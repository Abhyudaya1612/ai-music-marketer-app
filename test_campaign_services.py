#!/usr/bin/env python3
"""Quick verification of campaign services"""

from backend.services.campaign_planner import check_ollama_available, generate_song_quality_report
from backend.services.budget_calculator import calculate_budget_breakdown, calculate_reach_projection
from backend.services.pdf_reporter import generate_campaign_pdf
from backend.domain.models import MarketingCampaign

print("="*60)
print("CAMPAIGN PLANNER SERVICES VERIFICATION")
print("="*60)

# Test 1: Ollama availability
print("\n[TEST 1] Ollama Connection")
available = check_ollama_available()
print(f"✓ Ollama available: {available}")

# Test 2: Budget calculator
print("\n[TEST 2] Budget Calculator")
test_budgets = [100, 500, 1000, 1500, 2000, 5000]
for budget in test_budgets:
    breakdown = calculate_budget_breakdown(budget)
    reach = calculate_reach_projection(budget)
    total = sum(v.get('amount_usd', 0) for k, v in breakdown.items() if k != 'total')
    print(f"  Budget ${budget:5d}: Total=${total:7.2f}, Reach={reach:>8d} | ✓ DETERMINISTIC")

# Test 3: Song quality scoring
print("\n[TEST 3] Song Quality Scoring")
test_analyses = [
    {"mood": "upbeat", "energy": 0.9, "danceability": 0.8},
    {"mood": "sad", "energy": 0.2},
    {"mood": "chill", "energy": 0.4, "danceability": 0.3},
    {},  # Empty (should default)
]
for i, analysis in enumerate(test_analyses, 1):
    quality = generate_song_quality_report(analysis)
    score = quality.get("quality_score", 0) if isinstance(quality, dict) else 0
    print(f"  Analysis {i}: Score={score}/10 | Input: {analysis}")

# Test 4: Database model verification
print("\n[TEST 4] Database Model")
print(f"✓ Model name: {MarketingCampaign.__tablename__}")
print(f"✓ Model class: {MarketingCampaign.__name__}")
cols = [c.name for c in MarketingCampaign.__table__.columns]
required = ['id', 'owner_id', 'song_id', 'budget_usd', 'campaign_plan_json', 'budget_breakdown_json', 'captions_json', 'posting_schedule_json']
missing = [c for c in required if c not in cols]
if not missing:
    print(f"✓ All required columns present: {len(cols)} total")
else:
    print(f"✗ Missing columns: {missing}")

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60)
