"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

interface Campaign {
  campaign_id: string;
  song_id: string;
  song_title: string;
  artist_name: string | null;
  budget_usd: number;
  release_date: string | null;
  campaign_duration_days: number;
  target_audience: string | null;
  target_country: string | null;
  goals: string[];
  song_quality_score: number;
  budget_breakdown: {
    tier: string;
    allocations: Array<{
      channel: string;
      amount: number;
      percentage: number;
    }>;
  };
  campaign_plan: {
    pre_release: string[];
    release_week: string[];
    post_release: string[];
    positioning_usp: string;
  };
  captions_data: {
    instagram_captions: string[];
    tiktok_captions: string[];
    hashtags: string[];
  };
  posting_schedule: Array<{
    date: string;
    platform: string;
    content_type: string;
    posting_time: string;
    call_to_action: string;
  }>;
  created_at: string;
  updated_at: string;
}

const COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981"];

export default function CampaignDetailPage() {
  const router = useRouter();
  const params = useParams();
  const campaignId = params.id as string;

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"plan" | "captions" | "schedule">("plan");
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const fetchCampaign = async () => {
      try {
        const token = localStorage.getItem("api_token");
        if (!token) {
          setError("No API token found");
          setLoading(false);
          return;
        }

        const res = await fetch(`/api/v1/campaigns/${campaignId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          throw new Error("Failed to fetch campaign");
        }

        const data = await res.json();
        setCampaign(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading campaign");
      } finally {
        setLoading(false);
      }
    };

    if (campaignId) {
      fetchCampaign();
    }
  }, [campaignId]);

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this campaign?")) return;

    setDeleting(true);
    try {
      const token = localStorage.getItem("api_token");
      if (!token) throw new Error("No API token found");

      const res = await fetch(`/api/v1/campaigns/${campaignId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Failed to delete campaign");

      router.push("/campaigns");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error deleting campaign");
      setDeleting(false);
    }
  };

  const downloadPDF = async () => {
    try {
      const token = localStorage.getItem("api_token");
      if (!token) throw new Error("No API token found");

      const res = await fetch(`/api/v1/campaigns/${campaignId}/report.pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Failed to download PDF");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `campaign-${campaignId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error downloading PDF");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p>Loading campaign...</p>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-gray-600 mb-4">Campaign not found</p>
          <Link href="/campaigns" className="text-blue-600 hover:underline">
            Back to Campaigns
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold mb-2">{campaign.song_title}</h1>
              {campaign.artist_name && (
                <p className="text-gray-600">by {campaign.artist_name}</p>
              )}
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-blue-600">
                {campaign.song_quality_score}/10
              </div>
              <p className="text-sm text-gray-600">Quality Score</p>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={downloadPDF}
              className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition"
            >
              Download PDF
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
            >
              {deleting ? "Deleting..." : "Delete Campaign"}
            </button>
            <Link
              href="/campaigns"
              className="text-blue-600 hover:underline font-medium py-2 px-4"
            >
              Back to Campaigns
            </Link>
          </div>
        </div>

        {/* Campaign Info Cards */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Total Budget</p>
            <p className="text-2xl font-bold">${campaign.budget_usd.toLocaleString()}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Campaign Duration</p>
            <p className="text-2xl font-bold">{campaign.campaign_duration_days} days</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Target Country</p>
            <p className="text-2xl font-bold">{campaign.target_country || "US"}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-sm text-gray-600">Campaign Tier</p>
            <p className="text-2xl font-bold capitalize">
              {campaign.budget_breakdown?.tier || "Standard"}
            </p>
          </div>
        </div>

        {/* Budget Breakdown Chart */}
        {campaign.budget_breakdown?.allocations && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <h2 className="text-xl font-bold mb-4">Budget Allocation</h2>
            <div className="grid md:grid-cols-2 gap-8">
              <div className="flex items-center justify-center">
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={campaign.budget_breakdown.allocations.map((a) => ({
                        name: a.channel.replace(/_/g, " "),
                        value: a.amount,
                      }))}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {campaign.budget_breakdown.allocations.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value) => `$${(value as number).toFixed(2)}`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3">
                {campaign.budget_breakdown.allocations.map((alloc, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <div
                      className="w-4 h-4 rounded-full mt-1 flex-shrink-0"
                      style={{ backgroundColor: COLORS[idx % COLORS.length] }}
                    />
                    <div className="flex-1">
                      <p className="font-medium text-sm capitalize">
                        {alloc.channel.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-gray-600">
                        ${alloc.amount.toFixed(2)} ({alloc.percentage.toFixed(1)}%)
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-gray-200">
          {(["plan", "captions", "schedule"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-4 px-2 font-medium border-b-2 transition ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              {tab === "plan" && "Campaign Plan"}
              {tab === "captions" && "Content Ideas"}
              {tab === "schedule" && "Posting Schedule"}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow p-6">
          {/* Campaign Plan Tab */}
          {activeTab === "plan" && campaign.campaign_plan && (
            <div className="space-y-6">
              {campaign.campaign_plan.positioning_usp && (
                <div>
                  <h3 className="font-bold text-lg mb-2">Positioning</h3>
                  <p className="text-gray-700">{campaign.campaign_plan.positioning_usp}</p>
                </div>
              )}

              {["pre_release", "release_week", "post_release"].map((phase) => (
                <div key={phase}>
                  <button
                    onClick={() =>
                      setExpandedSection(
                        expandedSection === phase ? null : phase
                      )
                    }
                    className="font-bold text-lg w-full text-left py-2 hover:text-blue-600"
                  >
                    {phase === "pre_release" && "Pre-Release Strategy"}
                    {phase === "release_week" && "Release Week Tactics"}
                    {phase === "post_release" && "Post-Release Follow-up"}
                  </button>
                  {expandedSection === phase && (
                    <ul className="list-disc list-inside space-y-2 text-gray-700 ml-2">
                      {campaign.campaign_plan[
                        phase as keyof typeof campaign.campaign_plan
                      ] instanceof Array &&
                        (campaign.campaign_plan[
                          phase as keyof typeof campaign.campaign_plan
                        ] as string[]).map((tactic, idx) => (
                          <li key={idx}>{tactic}</li>
                        ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Captions Tab */}
          {activeTab === "captions" && campaign.captions_data && (
            <div className="space-y-6">
              <div>
                <h3 className="font-bold text-lg mb-3">Instagram Captions</h3>
                <div className="space-y-2">
                  {campaign.captions_data.instagram_captions?.slice(0, 3).map((cap, idx) => (
                    <p key={idx} className="text-gray-700 text-sm p-2 bg-gray-50 rounded">
                      {cap}
                    </p>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="font-bold text-lg mb-3">TikTok Ideas</h3>
                <div className="space-y-2">
                  {campaign.captions_data.tiktok_captions?.slice(0, 3).map((cap, idx) => (
                    <p key={idx} className="text-gray-700 text-sm p-2 bg-gray-50 rounded">
                      {cap}
                    </p>
                  ))}
                </div>
              </div>

              {campaign.captions_data.hashtags && (
                <div>
                  <h3 className="font-bold text-lg mb-2">Suggested Hashtags</h3>
                  <div className="flex flex-wrap gap-2">
                    {campaign.captions_data.hashtags.slice(0, 15).map((tag, idx) => (
                      <span
                        key={idx}
                        className="bg-blue-100 text-blue-800 text-sm px-2 py-1 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Posting Schedule Tab */}
          {activeTab === "schedule" && campaign.posting_schedule && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-3 py-2 text-left">Date</th>
                    <th className="px-3 py-2 text-left">Platform</th>
                    <th className="px-3 py-2 text-left">Content Type</th>
                    <th className="px-3 py-2 text-left">Time</th>
                    <th className="px-3 py-2 text-left">CTA</th>
                  </tr>
                </thead>
                <tbody>
                  {campaign.posting_schedule.slice(0, 14).map((post, idx) => (
                    <tr key={idx} className="border-b hover:bg-gray-50">
                      <td className="px-3 py-2">{post.date.slice(5)}</td>
                      <td className="px-3 py-2">{post.platform}</td>
                      <td className="px-3 py-2 text-xs">
                        {post.content_type.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-2 text-xs">{post.posting_time}</td>
                      <td className="px-3 py-2 text-xs">{post.call_to_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
