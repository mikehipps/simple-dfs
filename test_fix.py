#!/usr/bin/env python3
"""
Test script for the fixed CSV processor and optimizer
"""

from pydfs_lineup_optimizer import Site, Sport, get_optimizer
from pydfs_lineup_optimizer.solvers.mip_solver import MIPSolver

def test_optimizer():
    print("Testing fixed CSV processor and optimizer...")
    
    # Test the optimizer with the fixed processed CSV
    optimizer = get_optimizer(Site.FANDUEL, Sport.FOOTBALL)
    optimizer._solver = MIPSolver()

    print('Loading players from fixed processed CSV...')
    optimizer.load_players_from_csv('processed_lineup_data.csv')

    print('Player pool analysis:')
    print(f'Total players loaded: {len(optimizer.player_pool.all_players)}')
    print(f'Available positions: {optimizer.player_pool.available_positions}')

    # Check players by position
    positions_count = {}
    for player in optimizer.player_pool.all_players:
        for pos in player.positions:
            positions_count[pos] = positions_count.get(pos, 0) + 1

    print('Players by position:')
    for pos, count in sorted(positions_count.items()):
        print(f'  {pos}: {count} players')

    print('Setting constraints...')
    optimizer.set_min_salary_cap(59500)

    print('Attempting to generate lineups...')
    try:
        lineups = list(optimizer.optimize(1))
        print(f'Success! Generated {len(lineups)} lineups')
        if lineups:
            print('First lineup:')
            for player in lineups[0]:
                print(f'  {player.full_name} ({player.positions[0]}) - ${player.salary}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    test_optimizer()