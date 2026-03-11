"""
Live integration test: Run the hybrid duplicate matcher against the production database.
Compares results between old and new system.
"""
import os
import sys
import time

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import psycopg2
from psycopg2.extras import RealDictCursor
from duplicate_matcher import detect_duplicates

DATABASE_URL = "postgresql://logs_2m50_user:iBcJOf3ULl6M4fPWyUqAlXOZ28H3eSQ9@dpg-d53qe0v5r7bs73e0b420-a.oregon-postgres.render.com/logs_2m50"


def main():
    print("=" * 70)
    print("  Hybrid POI Matching - Live Integration Test")
    print("=" * 70)

    # 1. Connect and fetch POIs
    print("\n[1] Connecting to production database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_client_encoding('UTF8')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''SELECT "GlobalID", "Name_EN", "Name_AR", "Phone_Number",
                   "Category", "Latitude", "Longitude", "Building_Number",
                   "Floor_Number", "Commercial_License", "Website",
                   "Google_Map_URL"
                   FROM final_delivery''')
    pois = cur.fetchall()
    cur.close()
    conn.close()

    print(f"    Fetched {len(pois)} POIs from database")

    # 2. Run hybrid detection
    print("\n[2] Running hybrid duplicate detection...")
    start = time.time()
    result = detect_duplicates(
        pois,
        max_distance=100,
        match_threshold=85,
        possible_threshold=70,
        include_possible=True,
    )
    elapsed = time.time() - start
    print(f"    Completed in {elapsed:.2f}s")

    # 3. Results summary
    print(f"\n{'=' * 70}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total POIs analyzed:     {len(pois)}")
    print(f"  Duplicate groups found:  {result['total_groups']}")
    print(f"  POIs in groups:          {result['total_pois_in_groups']}")
    print(f"  MATCH pairs:             {len(result['match_pairs'])}")
    print(f"  POSSIBLE_MATCH pairs:    {len(result['possible_match_pairs'])}")
    print(f"  Total pairs:             {result['total_pairs']}")
    print(f"  Detection time:          {elapsed:.2f}s")

    # 4. Show MATCH pairs detail
    if result['match_pairs']:
        print(f"\n{'=' * 70}")
        print("  MATCH PAIRS (Score >= 85)")
        print(f"{'=' * 70}")
        for i, pair in enumerate(result['match_pairs'][:20], 1):
            print(f"\n  --- Pair {i} ---")
            print(f"    Source:    {pair['source_name']}")
            print(f"    Candidate: {pair['candidate_name']}")
            print(f"    Distance:  {pair['distance_m']}m")
            print(f"    Score:     {pair['final_score']}")
            print(f"    Name:      {pair['name_score']}  Distance: {pair['distance_score']}  "
                  f"Category: {pair['category_score']}  Phone: {pair['phone_score']}  "
                  f"Aux: {pair['auxiliary_score']}")
            print(f"    Reasons:   {', '.join(pair['match_reasons'])}")
            print(f"    Tier1:     {pair['tier1_match']}")
        if len(result['match_pairs']) > 20:
            print(f"\n    ... and {len(result['match_pairs']) - 20} more MATCH pairs")

    # 5. Show POSSIBLE_MATCH pairs
    if result['possible_match_pairs']:
        print(f"\n{'=' * 70}")
        print("  POSSIBLE MATCH PAIRS (Score 70-84)")
        print(f"{'=' * 70}")
        for i, pair in enumerate(result['possible_match_pairs'][:10], 1):
            print(f"\n  --- Pair {i} ---")
            print(f"    Source:    {pair['source_name']}")
            print(f"    Candidate: {pair['candidate_name']}")
            print(f"    Distance:  {pair['distance_m']}m")
            print(f"    Score:     {pair['final_score']}")
            print(f"    Reasons:   {', '.join(pair['match_reasons'])}")
        if len(result['possible_match_pairs']) > 10:
            print(f"\n    ... and {len(result['possible_match_pairs']) - 10} more POSSIBLE pairs")

    # 6. Score distribution
    all_scores = [p['final_score'] for p in result['match_pairs'] + result['possible_match_pairs']]
    if all_scores:
        print(f"\n{'=' * 70}")
        print("  SCORE DISTRIBUTION")
        print(f"{'=' * 70}")
        print(f"    Min score:  {min(all_scores):.1f}")
        print(f"    Max score:  {max(all_scores):.1f}")
        print(f"    Avg score:  {sum(all_scores)/len(all_scores):.1f}")
        bins = [(90, 100), (85, 90), (80, 85), (75, 80), (70, 75)]
        for lo, hi in bins:
            count = sum(1 for s in all_scores if lo <= s < hi)
            print(f"    {lo}-{hi}:      {count} pairs")

    print(f"\n{'=' * 70}")
    print("  TEST COMPLETE")
    print(f"{'=' * 70}\n")


if __name__ == '__main__':
    main()
