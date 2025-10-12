
#!/usr/bin/env python3
"""
NFL Lineup Generator using pydfs-lineup-optimizer with Dynamic Queue System
Generates exactly {TOTAL_LINEUPS} NFL lineups for FanDuel Classic contest from {CSV_FILE}
Uses {NUM_WORKERS} parallel workers with dynamic queue for optimal load balancing
Automatically selects strategy based on PROGRESSIVE_FACTOR:
- ProgressiveFantasyPointsStrategy when PROGRESSIVE_FACTOR > 0
- RandomFantasyPointsStrategy when PROGRESSIVE_FACTOR = 0
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
import pandas as pd
import queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydfs_lineup_optimizer import Site, Sport, get_optimizer
from pydfs_lineup_optimizer.exceptions import LineupOptimizerException
from pydfs_lineup_optimizer.fantasy_points_strategy import BaseFantasyPointsStrategy, ProgressiveFantasyPointsStrategy
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver

# Import configuration from external file
try:
    from inputs import (
        TOTAL_LINEUPS,
        NUM_WORKERS,
        LINEUPS_PER_BATCH,
        MAX_EXPOSURE,
        MAX_REPEATING_PLAYERS,
        MIN_SALARY,
        PROGRESSIVE_FACTOR,
        CSV_FILE
    )
except ImportError:
    print("ERROR: Configuration file 'inputs.py' not found.")
    print("Please copy 'inputs_template.py' to 'inputs.py' and modify the values as needed.")
    sys.exit(1)

# CSV preprocessing function for exact column matching
def preprocess_csv(input_file):
    """
    Preprocess CSV file with exact column matching for FanDuel NFL format
    
    Args:
        input_file (str): Path to input CSV file
        
    Returns:
        tuple: (processed_file_path, random_values_dict)
    """
    import pandas as pd
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting CSV preprocessing for: {input_file}")
    
    try:
        # Read the original CSV
        df = pd.read_csv(input_file)
        logger.info(f"Original CSV shape: {df.shape}")
        logger.info(f"Original columns: {list(df.columns)}")
        
        # Check for required columns with exact matching
        required_columns = ['B_Id', 'B_Position', 'B_Nickname', 'B_Salary', 'A_ppg_projection', 'B_Team', 'B_Opponent', 'Random']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Create random values dictionary for strategy
        random_values_dict = {}
        for _, row in df.iterrows():
            player_id = str(row['B_Id'])
            random_value = row['Random']
            if pd.notna(random_value):
                random_values_dict[player_id] = random_value
        
        logger.info(f"Created random values dictionary with {len(random_values_dict)} players")
        
        # Create processed DataFrame with exact column mapping
        processed_df = df[required_columns].copy()
        
        # Apply standard column mapping for FanDuel
        standard_mapping = {
            'B_Id': 'Id',
            'B_Position': 'Position',
            'B_Nickname': 'Nickname',
            'B_Salary': 'Salary',
            'A_ppg_projection': 'FPPG',
            'B_Team': 'Team',
            'B_Opponent': 'Opponent'
        }
        
        processed_df = processed_df.rename(columns=standard_mapping)
        
        # Split nickname into First Name and Last Name for FanDuel format
        processed_df['First Name'] = processed_df['Nickname'].apply(
            lambda x: x.split()[0] if pd.notna(x) else ''
        )
        processed_df['Last Name'] = processed_df['Nickname'].apply(
            lambda x: ' '.join(x.split()[1:]) if pd.notna(x) and len(x.split()) > 1 else ''
        )
        
        # Add required columns for FanDuel NFL
        processed_df['Injury Indicator'] = ''  # Empty injury indicator
        processed_df['Game'] = ''  # Empty game info
        processed_df['Roster Position'] = processed_df['Position']
        
        # Reorder columns to match FanDuel expected format
        fanduel_columns = ['Id', 'Position', 'First Name', 'Last Name', 'FPPG', 'Game', 'Team', 'Opponent', 'Salary', 'Injury Indicator', 'Roster Position']
        processed_df = processed_df[fanduel_columns]
        
        # Save processed CSV
        processed_file = 'processed_lineup_data.csv'
        processed_df.to_csv(processed_file, index=False)
        
        logger.info(f"Processed CSV saved as: {processed_file}")
        logger.info(f"Processed CSV shape: {processed_df.shape}")
        logger.info(f"Processed columns: {list(processed_df.columns)}")
        
        return processed_file, random_values_dict
        
    except Exception as e:
        logger.error(f"Error preprocessing CSV: {str(e)}")
        raise


# Global cancellation flag for graceful shutdown
cancellation_requested = threading.Event()


def setup_logging():
    """Configure logging for the script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('nfl_lineup_generator_dynamic.log')
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


class RandomFantasyPointsStrategy(BaseFantasyPointsStrategy):
    """
    Custom fantasy points strategy that uses the Random column from CSV
    to set min and max deviation for player projections.
    """
    
    def __init__(self, random_values_dict):
        """
        Initialize strategy with random values dictionary
        
        Args:
            random_values_dict (dict): Dictionary mapping player IDs to random percentage values
        """
        self.random_values_dict = random_values_dict
    
    def get_player_fantasy_points(self, player):
        """
        Get fantasy points for player with deviation based on Random column value
        
        Args:
            player: Player object
            
        Returns:
            float: Adjusted fantasy points with random deviation
        """
        player_id = str(player.id)
        
        if player_id in self.random_values_dict:
            random_percentage = self.random_values_dict[player_id]
            
            # Handle both string percentages (e.g., "7.50%") and float values
            if isinstance(random_percentage, str):
                # Convert percentage string to decimal (e.g., "7.50%" -> 0.075)
                random_decimal = float(random_percentage.strip('%')) / 100.0
            else:
                # Already a float value, use as decimal directly
                random_decimal = float(random_percentage) / 100.0
            
            # Calculate deviations: min = half of random, max = 2x random
            min_deviation = random_decimal / 3.0
            max_deviation = random_decimal * 3.0
            
            # Apply random deviation to player's FPPG
            import random
            deviation = random.uniform(min_deviation, max_deviation)
            direction = random.choice([-1, 1])
            
            adjusted_fppg = player.fppg * (1 + direction * deviation)
            return max(adjusted_fppg, 0)  # Ensure non-negative
        else:
            # Default behavior if player not found
            return player.fppg




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


def generate_lineups_dynamic_worker(thread_id, processed_csv, random_values_dict, work_queue, 
                                   file_lock, all_lineups, total_batches, process_start_time):
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
        logger.info(f"Thread {thread_id}: Initializing optimizer with MIP Solver")
        optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
        optimizer._solver = MIPSolver()  # Use MIP solver instead of default
        
        logger.info(f"Thread {thread_id}: Loading players from CSV")
        optimizer.load_players_from_csv(processed_csv)
        
        # Apply strategy based on PROGRESSIVE_FACTOR value
        if PROGRESSIVE_FACTOR > 0:
            # Use ProgressiveFantasyPointsStrategy only
            progressive_strategy = ProgressiveFantasyPointsStrategy(scale=PROGRESSIVE_FACTOR)
            optimizer.set_fantasy_points_strategy(progressive_strategy)
            logger.info(f"Thread {thread_id}: Using ProgressiveFantasyPointsStrategy with scale {PROGRESSIVE_FACTOR}")
        else:
            # Use RandomFantasyPointsStrategy only
            random_strategy = RandomFantasyPointsStrategy(random_values_dict)
            optimizer.set_fantasy_points_strategy(random_strategy)
            logger.info(f"Thread {thread_id}: Using RandomFantasyPointsStrategy with {len(random_values_dict)} players")
        
        # Apply constraints
        optimizer.set_max_repeating_players(MAX_REPEATING_PLAYERS)
        optimizer.set_min_salary_cap(MIN_SALARY)
        
        # Log active strategy
        strategy_info = f"ProgressiveFantasyPointsStrategy ({PROGRESSIVE_FACTOR})" if PROGRESSIVE_FACTOR > 0 else "RandomFantasyPointsStrategy"
        logger.info(f"Thread {thread_id}: Active constraints - "
                   f"Max exposure ({MAX_EXPOSURE*100}%), Max repeating players ({MAX_REPEATING_PLAYERS}), Min salary (${MIN_SALARY}), "
                   f"{strategy_info}, MIP Solver")
        
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
                    lineups = list(optimizer.optimize(LINEUPS_PER_BATCH, max_exposure=MAX_EXPOSURE))
                    
                    if not lineups:
                        logger.warning(f"Thread {thread_id}: No lineups generated in batch {batch_id+1}")
                        work_queue.task_done()
                        continue
                    
                    # Thread-safe addition to shared list
                    with file_lock:
                        all_lineups.extend(lineups)
                        total_generated += len(lineups)
                    
                    # Calculate timing
                    batch_duration = time.time() - batch_start_time
                    total_duration = time.time() - process_start_time
                    
                    logger.info(f"Thread {thread_id}: Batch {batch_id+1}/{total_batches} - "
                               f"Generated {len(lineups)} lineups "
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
        return thread_id, True, total_generated, None
        
    except Exception as e:
        logger.error(f"Thread {thread_id}: Unexpected error - {str(e)}")
        return thread_id, False, 0, f"Unexpected error: {str(e)}"


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
    lineups_dir = 'lineups'
    os.makedirs(lineups_dir, exist_ok=True)
    
    # Generate partial file names with timestamp and actual lineup count
    current_time = datetime.now()
    date_stamp = current_time.strftime("%m%d%Y-%H%M")  # MMDDYYYY-HHMM format
    lineup_count = len(all_lineups)
    
    # Use PARTIAL prefix and include actual lineup count
    lineup_filename = f"PARTIAL-{date_stamp}-{lineup_count}-fd-nfl-week6-lineups.csv"
    usage_filename = f"PARTIAL-{date_stamp}-{lineup_count}-fd-nfl-week6-player-usage.csv"
    
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
    """Generate exactly {TOTAL_LINEUPS} NFL lineups using dynamic queue system with {NUM_WORKERS} workers"""
    logger = logging.getLogger(__name__)
    process_start_time = time.time()
    
    try:
        # Preprocess the CSV file
        processed_csv, random_values_dict = preprocess_csv(CSV_FILE)
        
        # Create dynamic work queue with exact batch calculation
        work_queue, total_batches = create_work_queue(TOTAL_LINEUPS, LINEUPS_PER_BATCH)
        
        # Shared resources for threads
        file_lock = threading.Lock()
        all_lineups = []
        
        logger.info(f"Starting dynamic queue lineup generation with {NUM_WORKERS} workers")
        logger.info(f"Target: {TOTAL_LINEUPS} total lineups using dynamic queue system")
        logger.info(f"Configuration: {total_batches} batches × {LINEUPS_PER_BATCH} lineups = {TOTAL_LINEUPS} lineups exactly")
        # Log strategy selection
        if PROGRESSIVE_FACTOR > 0:
            logger.info(f"Using MIP Solver and ProgressiveFantasyPointsStrategy ({PROGRESSIVE_FACTOR})")
        else:
            logger.info(f"Using MIP Solver and RandomFantasyPointsStrategy with {len(random_values_dict)} players")
        logger.info(f"Active constraints: Max exposure ({MAX_EXPOSURE*100}%), Max repeating players ({MAX_REPEATING_PLAYERS}), Min salary (${MIN_SALARY})")
        logger.info("Dynamic queue system: Workers continuously pull batches until queue is empty")
        
        # Use ThreadPoolExecutor for better resource management
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            # Submit all worker tasks with dynamic queue
            future_to_thread = {
                executor.submit(generate_lineups_dynamic_worker, i, processed_csv, random_values_dict, 
                               work_queue, file_lock, all_lineups, total_batches, process_start_time): i
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
                    thread_id, success, lineups_count, error = result
                    completed_threads += 1
                    
                    if success:
                        successful_threads += 1
                        total_lineups_generated += lineups_count
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
            return lineup_filepath, usage_filepath, all_lineups
        
        # Calculate total process duration
        total_duration = time.time() - process_start_time
        
        # Check overall results
        logger.info(f"Worker execution completed: {successful_threads}/{NUM_WORKERS} workers successful in {total_duration:.1f}s")
        logger.info(f"Total lineups generated: {len(all_lineups)}")
        
        if not all_lineups:
            logger.error("No lineups were generated by any worker")
            return False
        
        # Create lineups directory if it doesn't exist
        lineups_dir = 'lineups'
        os.makedirs(lineups_dir, exist_ok=True)
        
        # Generate file names with dynamic timestamp and lineup count
        current_time = datetime.now()
        date_stamp = current_time.strftime("%m%d%Y-%H%M")  # MMDDYYYY-HHMM format
        lineup_count = len(all_lineups)
        
        lineup_filename = f"{date_stamp}-{TOTAL_LINEUPS}-fd-nfl-week6-lineups.csv"
        usage_filename = f"{date_stamp}-{TOTAL_LINEUPS}-fd-nfl-week6-player-usage.csv"
        
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
        
        return lineup_filepath, usage_filepath, all_lineups
        
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


def main():
    """Main function to run the lineup generator"""
    logger = setup_logging()
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Starting NFL Lineup Generator with Dynamic Queue System")
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
        lineup_filepath, usage_filepath, all_lineups = result
        
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
            
            logger.info("Lineup generation completed successfully!")
            logger.info(f"Lineups saved to: {lineup_filepath}")
            logger.info(f"Usage report saved to: {usage_filepath}")
    else:
        logger.error("Lineup generation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()