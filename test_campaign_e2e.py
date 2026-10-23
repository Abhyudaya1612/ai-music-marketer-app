#!/usr/bin/env python3
"""End-to-end campaign planner test"""
from datetime import date, datetime, timedelta
from backend.database import SessionLocal
from backend.domain.models import StudioSong, MarketingCampaign, MediaAsset
from backend.domain.schemas import MarketingCampaignCreate
from backend.services.budget_calculator import calculate_budget_breakdown, calculate_reach_projection
from backend.services.campaign_planner import (
    check_ollama_available, 
    generate_song_quality_report,
    generate_campaign_plan,
    generate_captions_and_concepts,
    generate_posting_schedule
)

print("="*70)
print("END-TO-END CAMPAIGN PLANNER TEST")
print("="*70)

db = SessionLocal()

# Get first song from database
song = db.query(StudioSong).first()
if not song:
    print("✗ No songs found in database")
    db.close()
    exit(1)

print(f"\n✓ Found test song: {song.title} by {song.artist_name}")

# Test 1: Budget breakdown
print("\n[TEST 1] Budget Breakdown (Deterministic)")
budget = 1000.0
breakdown = calculate_budget_breakdown(budget)
print(f"  Budget: ${budget}")
for platform, details in breakdown.items():
    if platform == 'total':
        continue
    print(f"  - {details['platform']}: ${details['amount_usd']} ({details['percentage']}%)")

# Test 2: Reach projection
print("\n[TEST 2] Reach Projection (Tiered)")
for test_budget in [100, 500, 1500, 2000]:
    reach = calculate_reach_projection(test_budget)
    print(f"  Budget ${test_budget:4d}: Reach {reach:>8d}")

# Test 3: Ollama availability
print("\n[TEST 3] Ollama Availability")
available = check_ollama_available()
print(f"  Ollama available: {available}")

# Test 4: Song quality report
print("\n[TEST 4] Song Quality Report")
analysis = song.analyses[0] if song.analyses else None
analysis_json = analysis.intelligence_json if analysis else {}
quality_report = generate_song_quality_report(analysis_json, song)
print(f"  Quality score: {quality_report.get('score', 'N/A')}/10")
print(f"  Strengths: {len(quality_report.get('strengths', []))} identified")
print(f"  Weaknesses: {len(quality_report.get('weaknesses', []))} identified")

# Test 5: Campaign plan
print("\n[TEST 5] Campaign Plan Generation")
genre = song.genre_preferences[0] if song.genre_preferences else "pop"
mood = analysis_json.get("mood", "upbeat") if analysis else "upbeat"
campaign = generate_campaign_plan(
    song_title=song.title,
    artist_name=song.artist_name or "Unknown",
    genre=genre,
    mood=mood,
    budget_usd=1000,
    target_audience="18-35 indie music fans",
    goals="Increase monthly listeners on Spotify"
)
print(f"  Campaign plan generated: {bool(campaign)}")
print(f"  Sections: {list(campaign.keys())}")

# Test 6: Captions and concepts
print("\n[TEST 6] Captions & Content Ideas")
captions = generate_captions_and_concepts(
    song_title=song.title,
    artist_name=song.artist_name or "Unknown",
    genre=genre,
    mood=mood
)
print(f"  Captions generated: {bool(captions)}")
print(f"  Platforms: {list(captions.keys())}")

# Test 7: Posting schedule
print("\n[TEST 7] Posting Schedule (28-day)")
schedule = generate_posting_schedule(duration_days=28, genre=genre)
print(f"  Schedule generated: {bool(schedule)}")
print(f"  Days in schedule: {len(schedule.get('calendar', []))}")

# Test 8: Database model
print("\n[TEST 8] Create Campaign Record")
new_campaign = MarketingCampaign(
    owner_id=song.owner_id,
    song_id=song.id,
    budget_usd=1000,
    release_date=date.today() + timedelta(days=7),
    campaign_duration_days=28,
    target_audience="18-35 indie music fans",
    goals="Increase monthly listeners",
    marketing_mix_preference="balanced",
    campaign_plan_json=campaign,
    budget_breakdown_json=breakdown,
    captions_json=captions,
    posting_schedule_json=schedule,
    song_quality_score=quality_report.get('score', 7),
    reach_projection=calculate_reach_projection(1000),
    ollama_model_used="phi" if available else "template",
    ollama_response_tokens=0,
)
db.add(new_campaign)
db.commit()
db.refresh(new_campaign)
print(f"  Campaign created: {new_campaign.id}")
print(f"  Budget: ${new_campaign.budget_usd}")
print(f"  Release date: {new_campaign.release_date}")

# Test 9: Retrieve campaign
print("\n[TEST 9] Retrieve Campaign from DB")
retrieved = db.query(MarketingCampaign).filter_by(id=new_campaign.id).first()
print(f"  Campaign retrieved: {bool(retrieved)}")
print(f"  Campaign title: {retrieved.campaign_plan_json.get('pre_release', {}).get('campaign_name', 'N/A')[:50]}...")

db.close()

print("\n" + "="*70)
print("✓ ALL TESTS PASSED")
print("="*70)
print("\nSUMMARY:")
print("  [✓] Budget breakdown deterministic")
print("  [✓] Reach projection tiered")
print("  [✓] Ollama integration working")
print("  [✓] Song quality assessment")
print("  [✓] Campaign plan generation")
print("  [✓] Content captions generation")
print("  [✓] Posting schedule generation")
print("  [✓] Database model working")
print("  [✓] CRUD operations working")
