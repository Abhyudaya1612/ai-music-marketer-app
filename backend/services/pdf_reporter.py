"""PDF report generation for marketing campaigns."""
from __future__ import annotations

import json
from datetime import date
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    PageTemplate,
    Frame,
)
from reportlab.pdfgen import canvas

from ..domain.models import MarketingCampaign, StudioSong


def generate_campaign_pdf(
    campaign: MarketingCampaign,
    song: StudioSong,
    intelligence_json: dict[str, Any] | None = None,
) -> bytes:
    """
    Generate a professional PDF report for a marketing campaign.
    
    Returns PDF as bytes.
    """
    # Create BytesIO buffer
    buffer = BytesIO()
    
    # Create PDF document
    pdf_doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"Campaign Report: {song.title}",
    )
    
    # Build styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=0.2 * inch,
        alignment=1,  # Center
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceAfter=0.15 * inch,
        spaceBefore=0.15 * inch,
    )
    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=10,
        alignment=4,  # Left
    )
    
    # Extract campaign data
    budget_breakdown = campaign.budget_breakdown_json or {}
    captions_data = campaign.captions_json or {}
    posting_schedule = campaign.posting_schedule_json or []
    campaign_plan = campaign.campaign_plan_json or {}
    song_quality_score = campaign.song_quality_score or 7
    
    # Build elements for PDF
    elements = []
    
    # --- Page 1: Cover Page ---
    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph(campaign.campaign_plan_json.get("positioning_usp", "Marketing Campaign Report") if campaign.campaign_plan_json else "AI Music Marketing Campaign", title_style))
    elements.append(Spacer(1, 0.3 * inch))
    
    cover_info = [
        [Paragraph(f"<b>Song:</b> {song.title}", normal_style)],
        [Paragraph(f"<b>Artist:</b> {song.artist_name or 'Unknown'}", normal_style)],
        [Paragraph(f"<b>Generated:</b> {date.today().strftime('%B %d, %Y')}", normal_style)],
        [Paragraph(f"<b>Campaign Budget:</b> ${campaign.budget_usd:,.2f}", normal_style)],
        [Paragraph(f"<b>Duration:</b> {campaign.campaign_duration_days} days", normal_style)],
    ]
    cover_table = Table(cover_info, colWidths=[6 * inch])
    cover_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(cover_table)
    elements.append(PageBreak())
    
    # --- Page 2: Executive Summary ---
    elements.append(Paragraph("Executive Summary", heading_style))
    
    summary_text = f"""
This marketing campaign has been designed to maximize awareness and engagement for <b>{song.title}</b> 
by <b>{song.artist_name or 'Unknown'}</b>. The campaign spans <b>{campaign.campaign_duration_days} days</b> 
with a total budget of <b>${campaign.budget_usd:,.2f}</b>.
<br/><br/>
The strategy focuses on multi-platform promotion across Instagram, TikTok, YouTube, and Spotify, 
with a balanced mix of organic and paid tactics. Success will be measured through streaming metrics, 
engagement rates, and audience growth.
<br/><br/>
<b>Song Quality Assessment:</b> {song_quality_score}/10
<br/>
This campaign is tailored to the song's strengths and target audience, with realistic expectations 
and proven promotional tactics.
"""
    elements.append(Paragraph(summary_text, normal_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(PageBreak())
    
    # --- Page 3: Song Analysis ---
    elements.append(Paragraph("Song Analysis & Market Positioning", heading_style))
    
    if campaign.campaign_plan_json:
        positioning = campaign.campaign_plan_json.get("positioning_usp", "")
        if positioning:
            elements.append(Paragraph(f"<b>Positioning:</b> {positioning}", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
    
    # Song quality info
    analysis_info = [
        [Paragraph("<b>Quality Score</b>", normal_style), Paragraph(f"{song_quality_score}/10", normal_style)],
        [Paragraph("<b>Genre</b>", normal_style), Paragraph(song.genre_preferences[0] if song.genre_preferences else "Unknown", normal_style)],
        [Paragraph("<b>Target Audience</b>", normal_style), Paragraph(campaign.target_audience or "Music fans in the genre", normal_style)],
        [Paragraph("<b>Target Country</b>", normal_style), Paragraph(campaign.target_country or "US", normal_style)],
    ]
    
    analysis_table = Table(analysis_info, colWidths=[1.5 * inch, 4.5 * inch])
    analysis_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
    ]))
    elements.append(analysis_table)
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(PageBreak())
    
    # --- Page 4: Budget Breakdown ---
    elements.append(Paragraph("Budget Allocation", heading_style))
    elements.append(Paragraph(f"Total Budget: <b>${campaign.budget_usd:,.2f}</b>", normal_style))
    elements.append(Spacer(1, 0.15 * inch))
    
    allocations = budget_breakdown.get("allocations", [])
    if allocations:
        budget_data = [["Channel", "Amount", "%", "Objective", "Expected Deliverables"]]
        for alloc in allocations:
            budget_data.append([
                alloc.get("channel", "").replace("_", " ").title(),
                f"${alloc.get('amount', 0):,.2f}",
                f"{alloc.get('percentage', 0):.1f}%",
                alloc.get("objective", "")[:40] + ("..." if len(alloc.get("objective", "")) > 40 else ""),
                alloc.get("expected_deliverables", "")[:50] + ("..." if len(alloc.get("expected_deliverables", "")) > 50 else ""),
            ])
        
        budget_table = Table(budget_data, colWidths=[1.2 * inch, 0.9 * inch, 0.6 * inch, 1.5 * inch, 1.8 * inch])
        budget_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ]))
        elements.append(budget_table)
    
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(PageBreak())
    
    # --- Page 5: Campaign Timeline ---
    elements.append(Paragraph("Campaign Strategy", heading_style))
    
    if campaign.campaign_plan_json:
        if "pre_release" in campaign.campaign_plan_json:
            elements.append(Paragraph("<b>Pre-Release (2-4 weeks before):</b>", normal_style))
            for tactic in campaign.campaign_plan_json.get("pre_release", [])[:3]:
                elements.append(Paragraph(f"• {tactic}", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
        
        if "release_week" in campaign.campaign_plan_json:
            elements.append(Paragraph("<b>Release Week:</b>", normal_style))
            for tactic in campaign.campaign_plan_json.get("release_week", [])[:4]:
                elements.append(Paragraph(f"• {tactic}", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
        
        if "post_release" in campaign.campaign_plan_json:
            elements.append(Paragraph("<b>Post-Release:</b>", normal_style))
            for tactic in campaign.campaign_plan_json.get("post_release", [])[:3]:
                elements.append(Paragraph(f"• {tactic}", normal_style))
    
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(PageBreak())
    
    # --- Page 6: Captions & Content ---
    elements.append(Paragraph("Social Media Captions & Ideas", heading_style))
    
    if captions_data:
        # Instagram captions sample
        if "instagram_captions" in captions_data:
            elements.append(Paragraph("<b>Instagram Reels Sample:</b>", normal_style))
            for caption in captions_data.get("instagram_captions", [])[:3]:
                elements.append(Paragraph(f"• {caption[:60]}...", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
        
        # TikTok captions sample
        if "tiktok_captions" in captions_data:
            elements.append(Paragraph("<b>TikTok Sample:</b>", normal_style))
            for caption in captions_data.get("tiktok_captions", [])[:3]:
                elements.append(Paragraph(f"• {caption[:60]}...", normal_style))
            elements.append(Spacer(1, 0.1 * inch))
        
        # Hashtags
        if "hashtags" in captions_data:
            hashtags = captions_data.get("hashtags", [])[:10]
            hashtags_str = " ".join(hashtags)
            elements.append(Paragraph(f"<b>Recommended Hashtags:</b> {hashtags_str}", normal_style))
    
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(PageBreak())
    
    # --- Page 7: Posting Schedule (sample) ---
    elements.append(Paragraph("Posting Schedule (Sample - First 2 Weeks)", heading_style))
    
    if posting_schedule:
        schedule_data = [["Date", "Platform", "Content Type", "Time", "CTA"]]
        for post in posting_schedule[:14]:  # First 2 weeks
            schedule_data.append([
                post.get("date", "")[:10],
                post.get("platform", ""),
                post.get("content_type", "").replace("_", " ").title(),
                post.get("posting_time", ""),
                post.get("call_to_action", "")[:30],
            ])
        
        schedule_table = Table(schedule_data, colWidths=[1.2 * inch, 1 * inch, 1.2 * inch, 0.8 * inch, 1.8 * inch])
        schedule_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9f9f9")]),
        ]))
        elements.append(schedule_table)
    
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(PageBreak())
    
    # --- Page 8: Performance Tracking & Assumptions ---
    elements.append(Paragraph("Performance Tracking & Key Metrics", heading_style))
    
    kpis_text = """
<b>Key Performance Indicators to Monitor:</b>
<br/>• Total streams in first 30 days
<br/>• New monthly listeners gained
<br/>• Playlist placements and reach
<br/>• Social media engagement rate and followers
<br/>• Website or link clicks from promotion
<br/>• Listener retention rate (repeat plays)
<br/><br/>
<b>Recommendations for Success:</b>
<br/>• Post consistently and monitor engagement daily
<br/>• Respond to all comments and messages
<br/>• Adjust paid ads based on early performance (first 48 hours)
<br/>• Track which platforms and content types perform best
<br/>• Reinvest high-performing content with additional paid promotion
<br/>• Analyze competitor strategies in your genre
<br/><br/>
<b>Assumptions & Limitations:</b>
<br/>• This plan is based on music industry best practices and data-driven research
<br/>• Actual results depend on execution quality, artist engagement, and market timing
<br/>• No streaming numbers or virality guarantees can be made
<br/>• The plan assumes consistent posting and community engagement
<br/>• Platform algorithms and audience behavior can change rapidly
<br/>• Success requires quality audio/video content and authentic artist presence
"""
    elements.append(Paragraph(kpis_text, normal_style))
    elements.append(Spacer(1, 0.3 * inch))
    
    # --- Footer ---
    footer_text = f"""
<i>Generated on {date.today().strftime('%B %d, %Y')}. This report is confidential and for the artist's use only. 
All recommendations are based on music industry best practices. Success depends on execution and market conditions.</i>
"""
    elements.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    pdf_doc.build(elements)
    
    # Get bytes
    buffer.seek(0)
    return buffer.getvalue()
