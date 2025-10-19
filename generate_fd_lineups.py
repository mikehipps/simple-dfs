#!/usr/bin/env python3
"""
Sports-Agnostic Lineup Generator using pydfs-lineup-optimizer with Dynamic Queue System
Generates exactly {TOTAL_LINEUPS} lineups for FanDuel Classic contest from {CSV_FILE}
Uses {NUM_WORKERS} parallel workers with dynamic queue for optimal load balancing
Features graceful cancellation support with Ctrl+C to save partial results

VIRTUAL ENVIRONMENT REMINDER:
Before running this script, activate the virtual environment:
    source venv/bin/activate  # On Linux/Mac
    venv\\Scripts\\activate     # On Windows

GRACEFUL CANCELLATION FEATURES:
- Press Ctrl+C at any time to gracefully stop the process
- All worker threads will be stopped cleanly
- Partial results will be saved with "PARTIAL-" prefix and actual lineup count
- Clear user feedback shows how many lineups were generated before interruption
"""

import os
import sys
import logging
import threading
import time
import signal
import queue
import random
import csv
import csv
from datetime import datetime
from itertools import islice
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydfs_lineup_optimizer import Site, Sport, get_optimizer
from pydfs_lineup_optimizer.exceptions import LineupOptimizerException
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver
from pydfs_lineup_optimizer.sites.fanduel.classic import settings
from custom_random_strategy import CustomRandomFantasyPointsStrategy
from sport_helpers import get_sport_helper



# Import configuration from external file
try:
    from fd_inputs import (
        TOTAL_LINEUPS,
        NUM_WORKERS,
        LINEUPS_PER_BATCH,
        MAX_EXPOSURE,
        MAX_REPEATING_PLAYERS,
        MIN_SALARY_OFFSET,
        CSV_FILE,
        SPORT_TYPE,
        OUTPUT_PREFIX,
        ENABLE_RANDOM
    )
except ImportError:
    print("ERROR: Configuration file 'fd_inputs.py' not found.")
    print("Please create 'fd_inputs.py' with the required configuration values.")
    sys.exit(1)

# Global cancellation flag for graceful shutdown
cancellation_requested = threading.Event()


def setup_logging():
    """Configure logging for the script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('fd_lineup_generator_dynamic.log')
        ]
    )
    return logging.getLogger(__name__)


def signal_handler(signum, frame):
    """
    Handle Ctrl+C (KeyboardInterrupt) signal for graceful shutdown
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger = logging.getLogger(__name__)
    logger.info("Interruption detected (Ctrl+C). Initiating graceful shutdown...")
    cancellation_requested.set()



def create_work_queue(total_lineups, lineups_per_batch):
    """
    Create a queue with all batch work items needed to generate exact lineup count
    
    Args:
        total_lineups (int): Total number of lineups to generate
        lineups_per_batch (int): Number of lineups per batch
        
    Returns:
        queue.Queue: Queue containing batch work items
    """
    # Calculate exact number of batches needed
    total_batches_needed = total_lineups // lineups_per_batch
    
    # Create queue with batch work items
    work_queue = queue.Queue()
    for batch_id in range(total_batches_needed):
        work_queue.put(batch_id)
    
    return work_queue, total_batches_needed


def get_sport_from_config():
    """
    Convert SPORT_TYPE configuration to pydfs-lineup-optimizer Sport enum
    
    Returns:
        Sport: The appropriate Sport enum value
    """
    sport_mapping = {
        "FOOTBALL": Sport.FOOTBALL,
        "BASKETBALL": Sport.BASKETBALL,
        "HOCKEY": Sport.HOCKEY,
        "BASEBALL": Sport.BASEBALL,
        "SOCCER": Sport.SOCCER,
        "GOLF": Sport.GOLF,
        "MMA": Sport.MMA,
        "NASCAR": Sport.NASCAR,
        "TENNIS": Sport.TENNIS,
        "LEAGUE_OF_LEGENDS": Sport.LEAGUE_OF_LEGENDS
    }
    
    sport_type = SPORT_TYPE.upper()
    if sport_type in sport_mapping:
        return sport_mapping[sport_type]
    else:
        logger = logging.getLogger(__name__)
        logger.warning(f"Unknown sport type '{SPORT_TYPE}'. Defaulting to FOOTBALL.")
        return Sport.FOOTBALL


def get_budget_from_sport():
    """
    Get budget constraint dynamically from pydfs settings classes
    based on SPORT_TYPE configuration
    """
    sport_type = SPORT_TYPE.upper()
    
    # Dynamically construct the class name
    settings_class_name = f"FanDuel{sport_type.title()}Settings"
    
    try:
        # Try to get the sport-specific settings class
        settings_class = getattr(settings, settings_class_name)
        return settings_class.budget
    except AttributeError:
        # Fall back to base FanDuelSettings if sport-specific class doesn't exist
        logger = logging.getLogger(__name__)
        logger.warning(f"Settings class '{settings_class_name}' not found. Using base FanDuelSettings.")
        return settings.FanDuelSettings.budget


def build_injury_status_map(csv_path):
    """
    Parse FanDuel CSV to build map of player ID -> injury indicator text.
    """
    status_map = {}
    try:
        with open(csv_path, 'r', newline='') as csv_file:
            start_line = 0
            while True:
                line = csv_file.readline()
                if 'FPPG' in line:
                    break
                if line == '':
                    return status_map
                start_line += 1
            csv_file.seek(0)
            for _ in range(start_line):
                csv_file.readline()
            reader = csv.DictReader(csv_file, skipinitialspace=True)
            for row in reader:
                player_id = (row.get('Id') or '').strip()
                if not player_id:
                    continue
                status = (row.get('Injury Indicator') or '').strip()
                status_map[player_id] = status
    except FileNotFoundError:
        pass
    return status_map


def apply_injury_filters(optimizer, injury_status_map, logger):
    """
    Allow questionable players while still excluding clear outs.
    """
    optimizer.player_pool.with_injured = True
    out_exact = {'O', 'OUT', 'IR', 'NA', 'IL', 'D'}
    out_prefixes = ('OUT', 'IR', 'SUS', 'SUSP', 'INA', 'INACT', 'LTIR', 'DOUBT', 'DNP', 'PUP')
    questionable_exact = {'Q', 'QUESTIONABLE', 'GTD', 'DTD', 'PROBABLE', 'PROB', 'DAYTODAY', 'P'}
    questionable_prefixes = ('QUEST', 'GTD', 'DTD', 'PROB', 'DAYTODAY')
    removed = 0
    questionable = 0

    for player in list(optimizer.player_pool.all_players):
        status_raw = injury_status_map.get(player.id, '')
        if not status_raw:
            continue
        normalized = status_raw.strip().upper().replace('.', '').replace('-', '').replace(' ', '')
        if not normalized:
            continue
        if normalized in out_exact or normalized.startswith(out_prefixes):
            optimizer.player_pool.remove_player(player)
            removed += 1
        elif normalized in questionable_exact or normalized.startswith(questionable_prefixes):
            questionable += 1

    if removed:
        logger.info(f"Filtered out {removed} players marked as OUT/IR/etc.")
    if questionable:
        logger.info(f"Retained {questionable} players with questionable statuses for optimization.")


def generate_lineups_dynamic_worker(thread_id, processed_csv, random_values_dict, work_queue,
                                   file_lock, all_lineups, total_batches, process_start_time,
                                   injury_status_map):
    """
    Worker function that continuously processes batches from the shared queue
    
    Args:
        thread_id (int): Thread identifier
        processed_csv (str): Path to processed CSV file
        random_values_dict (dict): Dictionary mapping player IDs to random percentage values
        work_queue (queue.Queue): Shared queue containing batch work items
        file_lock (threading.Lock): Lock for thread-safe file operations
        all_lineups (list): Shared list to collect all generated lineups
        total_batches (int): Total number of batches in the queue
        process_start_time (float): Timestamp when the overall process started
        
    Returns:
        tuple: (thread_id, success, lineups_generated, error_message)
    """
    logger = logging.getLogger(__name__)
    thread_start_time = time.time()
    total_generated = 0
    
    try:
        # Get sport helper for the configured sport type
        sport_helper_class = get_sport_helper(SPORT_TYPE)
        sport_helper = sport_helper_class()
        sport_helper.load_metadata(processed_csv)
        rng = random.Random()
        
        # Get sport from configuration
        sport = get_sport_from_config()
        
        logger.info(f"Thread {thread_id}: Initializing optimizer with MIP Solver for {SPORT_TYPE}")
        optimizer = get_optimizer(Site.FANDUEL, sport)
        optimizer._solver = MIPSolver()  # Use MIP solver instead of default
        
        # Apply CustomRandomFantasyPointsStrategy if enabled
        if ENABLE_RANDOM:
            logger.info(f"Thread {thread_id}: Using CustomRandomFantasyPointsStrategy with Min/Max Deviation columns")
            optimizer.set_fantasy_points_strategy(CustomRandomFantasyPointsStrategy())
        else:
            logger.info(f"Thread {thread_id}: Using standard projection-based optimization")
        
        logger.info(f"Thread {thread_id}: Loading players from CSV")
        optimizer.load_players_from_csv(processed_csv)
        apply_injury_filters(optimizer, injury_status_map, logger)
        
        # Apply sport-specific constraints using helper
        sport_helper.apply_constraints(optimizer)
        
        # Get budget from sport helper and calculate min salary using offset
        budget = sport_helper.get_budget()
        min_salary_offset = sport_helper.get_min_salary_offset()
        min_salary = int(budget * (1 - min_salary_offset))
        
        # Apply common constraints
        optimizer.set_max_repeating_players(MAX_REPEATING_PLAYERS)
        optimizer.set_min_salary_cap(min_salary)
        
        # Perform sport-specific pre-optimization setup
        sport_helper.pre_optimization_setup(optimizer)
        
        logger.info(f"Thread {thread_id}: Active constraints - "
                   f"Max exposure ({MAX_EXPOSURE*100}%), Max repeating players ({MAX_REPEATING_PLAYERS}), Min salary (${min_salary}), "
                   f"MIP Solver, Sport-specific constraints applied, "
                   f"Random Strategy: {'ENABLED' if ENABLE_RANDOM else 'DISABLED'}")
        
        # Continuously process batches from the queue until empty
        while not cancellation_requested.is_set():
            try:
                # Get next batch from queue with timeout to check cancellation
                batch_id = work_queue.get(timeout=1)
                
                # Calculate queue progress
                queue_size = work_queue.qsize()
                batches_remaining = queue_size + 1  # +1 for current batch
                batches_completed = total_batches - batches_remaining
                
                batch_start_time = time.time()
                
                logger.info(f"Thread {thread_id}: Batch {batch_id+1}/{total_batches} - "
                           f"Queue: {batches_completed}/{total_batches} batches completed - "
                           f"Generating {LINEUPS_PER_BATCH} lineups")
                
                try:
                    sport_helper.apply_random_bias(optimizer, rng)
                    lineups = list(optimizer.optimize(LINEUPS_PER_BATCH, max_exposure=MAX_EXPOSURE))
                    
                    if not lineups:
                        logger.warning(f"Thread {thread_id}: No lineups generated in batch {batch_id+1}")
                        work_queue.task_done()
                        continue
                    
                    # Apply sport-specific post-processing
                    processed_lineups = sport_helper.post_optimization_processing(lineups)
                    
                    # Thread-safe addition to shared list
                    with file_lock:
                        all_lineups.extend(processed_lineups)
                        total_generated += len(processed_lineups)
                    
                    # Calculate timing
                    batch_duration = time.time() - batch_start_time
                    total_duration = time.time() - process_start_time
                    
                    logger.info(f"Thread {thread_id}: Batch {batch_id+1}/{total_batches} - "
                               f"Generated {len(processed_lineups)} lineups "
                               f"({batch_duration:.1f}s : {total_duration:.1f}s)")
                    
                except LineupOptimizerException as e:
                    logger.error(f"Thread {thread_id}: Optimizer error in batch {batch_id+1} - {str(e)}")
                except Exception as e:
                    logger.error(f"Thread {thread_id}: Unexpected error in batch {batch_id+1} - {str(e)}")
                
                # Mark batch as completed
                work_queue.task_done()
                
            except queue.Empty:
                # Queue is empty, worker can exit
                break
        
        thread_duration = time.time() - thread_start_time
        logger.info(f"Thread {thread_id}: Completed with {total_generated} total lineups generated in {thread_duration:.1f}s")
        return thread_id, True, total_generated, None, sport_helper.get_random_bias_summary()
    
    except Exception as e:
        logger.error(f"Thread {thread_id}: Unexpected error - {str(e)}")
        return thread_id, False, 0, f"Unexpected error: {str(e)}", None


def _extract_output_subdir():
    """
    Determine sport-specific subdirectory for lineup exports based on OUTPUT_PREFIX.
    Falls back to the sport type abbreviation if no 3-letter token is present.
    """
    tokens = [token for token in OUTPUT_PREFIX.replace('_', '-').split('-') if token]
    for token in tokens:
        if len(token) == 3 and token.isalpha():
            return token.lower()
    return SPORT_TYPE.lower()[:3]


def _get_lineups_output_dir():
    subdir = _extract_output_subdir()
    lineups_dir = os.path.join('lineups', subdir)
    os.makedirs(lineups_dir, exist_ok=True)
    return lineups_dir


def save_partial_results(all_lineups, process_start_time):
    """
    Save partial results when interruption is detected
    
    Args:
        all_lineups (list): List of generated lineups so far
        process_start_time (float): Timestamp when the process started
    
    Returns:
        tuple: (lineup_filepath, usage_filepath) or (None, None) if no lineups
    """
    logger = logging.getLogger(__name__)
    
    if not all_lineups:
        logger.warning("No lineups generated to save as partial results")
        return None, None
    
    # Create lineups directory if it doesn't exist
    lineups_dir = _get_lineups_output_dir()
    
    # Generate partial file names with timestamp and actual lineup count
    current_time = datetime.now()
    date_stamp = current_time.strftime("%m%d%Y-%H%M")  # MMDDYYYY-HHMM format
    lineup_count = len(all_lineups)
    
    # Use PARTIAL prefix and include actual lineup count
    lineup_filename = f"PARTIAL-{date_stamp}-{lineup_count}-{OUTPUT_PREFIX}-{SPORT_TYPE.lower()}-lineups.csv"
    usage_filename = f"PARTIAL-{date_stamp}-{lineup_count}-{OUTPUT_PREFIX}-{SPORT_TYPE.lower()}-player-usage.csv"
    
    lineup_filepath = os.path.join(lineups_dir, lineup_filename)
    usage_filepath = os.path.join(lineups_dir, usage_filename)
    
    # Save all lineups to CSV
    logger.info(f"Saving {len(all_lineups)} partial lineups to {lineup_filepath}")
    
    # Export lineups using the lineup_exporter
    from pydfs_lineup_optimizer.lineup_exporter import CSVLineupExporter
    
    exporter = CSVLineupExporter(all_lineups)
    exporter.export(lineup_filepath)
    
    total_duration = time.time() - process_start_time
    logger.info(f"Partial results saved: {len(all_lineups)} lineups generated in {total_duration:.1f}s")
    logger.info(f"Partial lineups saved to: {lineup_filepath}")
    logger.info(f"Partial usage report will be saved to: {usage_filepath}")
    
    return lineup_filepath, usage_filepath


def generate_lineups_dynamic():
    """Generate exactly {TOTAL_LINEUPS} lineups using dynamic queue system with {NUM_WORKERS} workers"""
    logger = logging.getLogger(__name__)
    process_start_time = time.time()
    
    try:
        # Always use the original CSV file directly
        processed_csv = CSV_FILE
        random_values_dict = {}
        logger.info(f"Using original {SPORT_TYPE} CSV file directly: {CSV_FILE}")
        injury_status_map = build_injury_status_map(processed_csv)
        if injury_status_map:
            logger.info("Parsed injury indicators from CSV (questionable players will remain eligible).")
        else:
            logger.warning("Could not parse injury indicators; default injury filtering will apply.")
        
        # Create dynamic work queue with exact batch calculation
        work_queue, total_batches = create_work_queue(TOTAL_LINEUPS, LINEUPS_PER_BATCH)
        
        # Shared resources for threads
        file_lock = threading.Lock()
        all_lineups = []
        
        # Get sport helper for logging configuration
        sport_helper_class = get_sport_helper(SPORT_TYPE)
        sport_helper = sport_helper_class()
        sport_config = sport_helper.get_sport_specific_config()
        
        logger.info(f"Starting dynamic queue lineup generation with {NUM_WORKERS} workers for {SPORT_TYPE}")
        logger.info(f"Target: {TOTAL_LINEUPS} total lineups using dynamic queue system")
        logger.info(f"Configuration: {total_batches} batches × {LINEUPS_PER_BATCH} lineups = {TOTAL_LINEUPS} lineups exactly")
        logger.info(f"Using MIP Solver with {'CustomRandomFantasyPointsStrategy' if ENABLE_RANDOM else 'default optimizer strategy'}")
        # Calculate min salary for logging using sport helper
        budget = sport_helper.get_budget()
        min_salary_offset = sport_helper.get_min_salary_offset()
        min_salary = int(budget * (1 - min_salary_offset))
        logger.info(f"Active constraints: Max exposure ({MAX_EXPOSURE*100}%), Max repeating players ({MAX_REPEATING_PLAYERS}), Min salary (${min_salary})")
        logger.info(f"Sport-specific constraints: {sport_config.get('constraints', ['None'])}")
        logger.info(f"Custom Random Fantasy Points Strategy: {'ENABLED' if ENABLE_RANDOM else 'DISABLED'}")
        logger.info("Dynamic queue system: Workers continuously pull batches until queue is empty")
        
        # Use ThreadPoolExecutor for better resource management
        combined_flip_summary = {}

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            # Submit all worker tasks with dynamic queue
            future_to_thread = {
                executor.submit(generate_lineups_dynamic_worker, i, processed_csv, random_values_dict,
                               work_queue, file_lock, all_lineups, total_batches, process_start_time,
                               injury_status_map): i
                for i in range(NUM_WORKERS)
            }
            
            # Collect results as they complete
            completed_threads = 0
            successful_threads = 0
            total_lineups_generated = 0
            
            for future in as_completed(future_to_thread):
                thread_id = future_to_thread[future]
                try:
                    result = future.result()
                    thread_id, success, lineups_count, error, flip_summary = result
                    completed_threads += 1
                    
                    if success:
                        successful_threads += 1
                        total_lineups_generated += lineups_count
                        if flip_summary:
                            for key, value in flip_summary.items():
                                combined_flip_summary[key] = combined_flip_summary.get(key, 0) + value
                        logger.info(f"Thread {thread_id} completed successfully with {lineups_count} lineups")
                    else:
                        logger.error(f"Thread {thread_id} failed: {error}")
                        
                except Exception as e:
                    logger.error(f"Thread {thread_id} generated an exception: {str(e)}")
                    completed_threads += 1
        
        # Check if cancellation was requested
        if cancellation_requested.is_set():
            logger.info("Graceful shutdown completed. Saving partial results...")
            lineup_filepath, usage_filepath = save_partial_results(all_lineups, process_start_time)
            
            logger.info(f"Graceful shutdown complete. {len(all_lineups)} lineups saved as partial results.")
            return lineup_filepath, usage_filepath, all_lineups, combined_flip_summary
        
        # Calculate total process duration
        total_duration = time.time() - process_start_time
        
        # Check overall results
        logger.info(f"Worker execution completed: {successful_threads}/{NUM_WORKERS} workers successful in {total_duration:.1f}s")
        logger.info(f"Total lineups generated: {len(all_lineups)}")
        
        if not all_lineups:
            logger.error("No lineups were generated by any worker")
            return False
        
        # Create lineups directory if it doesn't exist
        lineups_dir = _get_lineups_output_dir()
        
        # Generate file names with dynamic timestamp and lineup count
        current_time = datetime.now()
        date_stamp = current_time.strftime("%m%d%Y-%H%M")  # MMDDYYYY-HHMM format
        lineup_count = len(all_lineups)
        
        lineup_filename = f"{date_stamp}-{TOTAL_LINEUPS}-{OUTPUT_PREFIX}-{SPORT_TYPE.lower()}-lineups.csv"
        usage_filename = f"{date_stamp}-{TOTAL_LINEUPS}-{OUTPUT_PREFIX}-{SPORT_TYPE.lower()}-player-usage.csv"
        
        lineup_filepath = os.path.join(lineups_dir, lineup_filename)
        usage_filepath = os.path.join(lineups_dir, usage_filename)
        
        # Save all lineups to CSV
        logger.info(f"Saving {len(all_lineups)} lineups to {lineup_filepath}")
        
        # Export lineups using the lineup_exporter
        from pydfs_lineup_optimizer.lineup_exporter import CSVLineupExporter
        
        exporter = CSVLineupExporter(all_lineups)
        exporter.export(lineup_filepath)
        
        # Print first few lineups for verification
        logger.info("First 3 generated lineups:")
        for i, lineup in enumerate(all_lineups[:3], 1):
            logger.info(f"Lineup {i}:")
            logger.info(f"  Projected Points: {lineup.fantasy_points_projection:.2f}")
            logger.info(f"  Salary Used: ${lineup.salary_costs}")
            for player in lineup.players:
                logger.info(f"    {player.full_name} - {player.positions[0]} - ${player.salary}")
        
        logger.info(f"Successfully generated {len(all_lineups)} lineups across {successful_threads} workers in {total_duration:.1f}s")
        logger.info(f"Lineups saved to: {lineup_filepath}")
        logger.info(f"Player usage report will be saved to: {usage_filepath}")
        
        return lineup_filepath, usage_filepath, all_lineups, combined_flip_summary
        
    except Exception as e:
        logger.error(f"Error in parallel lineup generation: {str(e)}")
        return False


def generate_player_usage_report(lineups, output_file):
    """
    Generate player usage report from lineups
    
    Args:
        lineups (list): List of generated lineups
        output_file (str): Path to output CSV file
    """
    logger = logging.getLogger(__name__)
    
def generate_player_usage_report(lineups, output_file):
    """
    Generate player usage report from lineups
    
    Args:
        lineups (list): List of generated lineups
        output_file (str): Path to output CSV file
    """
    logger = logging.getLogger(__name__)
    
    try:
        from collections import defaultdict
        
        # Dictionary to store player usage
        player_usage = defaultdict(lambda: {'count': 0, 'positions': set()})
        
        # Analyze player usage across all lineups
        for lineup in lineups:
            for player in lineup.players:
                player_name = player.full_name
                position = player.positions[0] if player.positions else 'Unknown'
                
                player_usage[player_name]['count'] += 1
                player_usage[player_name]['positions'].add(position)
        
        # Generate report data
        report_data = []
        total_lineups = len(lineups)
        
        for player, data in player_usage.items():
            count = data['count']
            positions = ', '.join(sorted(data['positions']))
            percentage = (count / total_lineups) * 100
            report_data.append((player, positions, count, percentage))
        
        # Sort by usage count (highest to lowest)
        report_data.sort(key=lambda x: x[2], reverse=True)
        
        # Save to CSV
        import csv
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Write header
            writer.writerow(['Player Name', 'Positions', 'Times Used', 'Usage Percentage (%)'])
            
            # Write data
            for player, positions, count, percentage in report_data:
                writer.writerow([player, positions, count, f"{percentage:.2f}"])
        
        logger.info(f"Player usage report saved to: {output_file}")
        logger.info(f"Analyzed {total_lineups} lineups with {len(report_data)} unique players")
        
        # Display top 10 most used players
        logger.info("Top 10 most used players:")
        for i, (player, positions, count, percentage) in enumerate(report_data[:10], 1):
            logger.info(f"  {i:2d}. {player:<20} {positions:<12} {count:2d} times ({percentage:.1f}%)")
        
        return True
        
    except Exception as e:
        logger.error(f"Error generating player usage report: {str(e)}")
        return False


def load_hockey_metadata(csv_path):
    meta = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                pid = row.get('Id')
                if not pid:
                    continue
                line_raw = row.get('HockeyLine')
                pp_raw = row.get('HockeyPPLine')
                team = row.get('Team')
                meta[pid] = {
                    'line': _normalize_unit(line_raw),
                    'pp': _normalize_unit(pp_raw),
                    'team': team
                }
    except FileNotFoundError:
        logging.getLogger(__name__).warning("Metadata CSV not found: %s", csv_path)
    return meta


def _normalize_unit(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return None
    try:
        return str(int(float(text)))
    except (ValueError, TypeError):
        return text


def generate_lineup_summary(lineups, metadata, flip_summary, output_file, sport_type):
    logger = logging.getLogger(__name__)
    try:
        total_lineups = len(lineups)
        if total_lineups == 0:
            return False

        from collections import Counter, defaultdict
        import statistics
        sport_upper = sport_type.upper()

        projections = [lu.fantasy_points_projection for lu in lineups]
        salaries = [lu.salary_costs for lu in lineups]

        max_team_stack_dist = Counter()
        lineup_unique_teams = Counter()
        team_exposure = Counter()
        line_stack_counts = Counter()
        pp_stack_counts = Counter()
        player_exposure = Counter()
        position_counts = Counter()

        for lineup in lineups:
            team_counts = Counter(p.team for p in lineup.players)
            for team, count in team_counts.items():
                team_exposure[team] += 1
            max_team_stack_dist[max(team_counts.values())] += 1
            lineup_unique_teams[len(team_counts)] += 1
            for player in lineup.players:
                player_exposure[player.full_name] += 1
                for pos in player.positions:
                    position_counts[pos] += 1

            # Line/PP stacks
            team_line_counts = defaultdict(lambda: defaultdict(int))
            team_pp_counts = defaultdict(lambda: defaultdict(int))
            for player in lineup.players:
                meta = metadata.get(player.id, {}) if metadata else {}
                line = meta.get('line')
                pp = meta.get('pp')
                if line:
                    team_line_counts[player.team][line] += 1
                if pp:
                    team_pp_counts[player.team][pp] += 1
            for team, counts in team_line_counts.items():
                for line, count in counts.items():
                    if count >= 2:
                        key = f"{team} line {line} ({count})"
                        line_stack_counts[key] += 1
            for team, counts in team_pp_counts.items():
                for pp, count in counts.items():
                    if count >= 2:
                        key = f"{team} PP{pp} ({count})"
                        pp_stack_counts[key] += 1

        with open(output_file, 'w', encoding='utf-8') as fh:
            fh.write(f"Total lineups: {total_lineups}\n")
            fh.write(f"Average projection: {statistics.mean(projections):.2f}\n")
            fh.write(f"Projection range: {min(projections):.2f} – {max(projections):.2f}\n")
            fh.write(f"Average salary: {statistics.mean(salaries):.0f}\n")
            fh.write("\nTeam stack distribution (max players from one team per lineup):\n")
            for stack_size in sorted(max_team_stack_dist):
                count = max_team_stack_dist[stack_size]
                fh.write(f"  {stack_size} players: {count} lineups ({count/total_lineups:.1%})\n")

            fh.write("\nUnique teams per lineup distribution:\n")
            for unique_count in sorted(lineup_unique_teams):
                count = lineup_unique_teams[unique_count]
                fh.write(f"  {unique_count} teams: {count} lineups ({count/total_lineups:.1%})\n")

            fh.write("\nTop team exposures:\n")
            if team_exposure:
                for team, count in team_exposure.most_common(10):
                    fh.write(f"  {team}: {count} lineups ({count/total_lineups:.1%})\n")
            else:
                fh.write("  None\n")

            fh.write("\nTop player exposures:\n")
            if player_exposure:
                for name, count in player_exposure.most_common(15):
                    fh.write(f"  {name}: {count} lineups ({count/total_lineups:.1%})\n")
            else:
                fh.write("  None\n")

            fh.write("\nPosition counts across all lineups:\n")
            if position_counts:
                for pos, count in position_counts.most_common():
                    fh.write(f"  {pos}: {count} selections ({count/(total_lineups):.2f} per lineup)\n")
            else:
                fh.write("  None\n")

            if sport_upper in ("HOCKEY", "NHL"):
                fh.write("\nLine stacks (>=2 players same team & line):\n")
                if line_stack_counts:
                    for key, count in line_stack_counts.most_common(10):
                        fh.write(f"  {key}: {count}\n")
                else:
                    fh.write("  None\n")

                fh.write("\nPower-play stacks (>=2 players same team & PP unit):\n")
                if pp_stack_counts:
                    for key, count in pp_stack_counts.most_common(10):
                        fh.write(f"  {key}: {count}\n")
                else:
                    fh.write("  None\n")

            if flip_summary:
                fh.write("\nRandom bias flip summary:\n")
                label_map = {
                    "batches": "Batches processed",
                    "team_hits": "Team flips won",
                    "line1_hits": "Line 1 flips won",
                    "line2_hits": "Line 2 flips won",
                    "pp1_hits": "PP1 flips won",
                    "pp2_hits": "PP2 flips won",
                    "goalie_bonus_hits": "Goalie/Line1D bonuses",
                    "team_flips": "Team flips won",
                    "pass_flips": "Passing flips won",
                    "rush_flips": "Rushing flips won",
                    "team_players_boosted": "Players boosted by team flips",
                    "pass_players_boosted": "Players boosted by pass flips",
                    "rush_players_boosted": "Players boosted by rush flips",
                }
                for key, value in sorted(flip_summary.items()):
                    label = label_map.get(key, key.replace('_', ' ').title())
                    fh.write(f"  {label}: {value}\n")

        return True
    except Exception as e:
        logger.error(f"Error generating lineup summary: {e}")
        return False


def main():
    """Main function to run the lineup generator"""
    logger = setup_logging()
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info(f"Starting {SPORT_TYPE} Lineup Generator with Dynamic Queue System")
    logger.info("=" * 50)
    logger.info("Press Ctrl+C at any time to gracefully stop the process and save partial results")
    logger.info("=" * 50)
    
    # Check if input file exists
    if not os.path.exists(CSV_FILE):
        logger.error(f"Input file '{CSV_FILE}' not found")
        sys.exit(1)
    
    # Generate lineups
    result = generate_lineups_dynamic()
    
    if result:
        lineup_filepath, usage_filepath, all_lineups, flip_summary = result
        
        # Check if this was a partial result due to cancellation
        if cancellation_requested.is_set():
            logger.info("=" * 50)
            logger.info("PROCESS INTERRUPTED - PARTIAL RESULTS SAVED")
            logger.info(f"Successfully saved {len(all_lineups)} lineups before interruption")
            logger.info(f"Partial lineups saved to: {lineup_filepath}")
            logger.info(f"Partial usage report saved to: {usage_filepath}")
            logger.info("=" * 50)
        else:
            # Generate player usage report for complete results
            logger.info("Generating player usage report...")
            success = generate_player_usage_report(all_lineups, usage_filepath)
            
            if success:
                logger.info("Player usage report generated successfully!")
            else:
                logger.error("Player usage report generation failed!")
            
            summary_path = lineup_filepath.replace("-lineups.csv", "-summary.txt")
            metadata = None
            if SPORT_TYPE.upper() in ("HOCKEY", "NHL"):
                metadata = load_hockey_metadata(CSV_FILE)
            if generate_lineup_summary(all_lineups, metadata, flip_summary, summary_path, SPORT_TYPE):
                logger.info(f"Lineup summary saved to: {summary_path}")
            else:
                logger.warning("Failed to generate lineup summary.")
            logger.info("Lineup generation completed successfully!")
            logger.info(f"Lineups saved to: {lineup_filepath}")
            logger.info(f"Usage report saved to: {usage_filepath}")
    else:
        logger.error("Lineup generation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
