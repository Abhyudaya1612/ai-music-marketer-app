"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface Campaign {
  campaign_id: string;
  song_id: string;
  song_title: string;
  artist_name: string | null;
  budget_usd: number;
  release_date: string | null;
  created_at: string;
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCampaigns = async () => {
      try {
        const token = localStorage.getItem("api_token");
        if (!token) {
          setError("No API token found");
          setLoading(false);
          return;
        }

        const res = await fetch("/api/v1/campaigns", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          throw new Error("Failed to fetch campaigns");
        }

        const data = await res.json();
        setCampaigns(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading campaigns");
      } finally {
        setLoading(false);
      }
    };

    fetchCampaigns();
  }, []);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p>Loading campaigns...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Marketing Campaigns</h1>
          <Link
            href="/campaigns/new"
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
          >
            New Campaign
          </Link>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {campaigns.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <p className="text-gray-600 mb-6">No campaigns yet. Create one to get started.</p>
            <Link
              href="/campaigns/new"
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
            >
              Create Your First Campaign
            </Link>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {campaigns.map((campaign) => (
              <Link
                key={campaign.campaign_id}
                href={`/campaigns/${campaign.campaign_id}`}
                className="bg-white rounded-lg shadow hover:shadow-lg transition p-6"
              >
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {campaign.song_title}
                </h3>
                {campaign.artist_name && (
                  <p className="text-sm text-gray-600 mb-3">{campaign.artist_name}</p>
                )}
                <div className="space-y-2 text-sm text-gray-600">
                  <p>
                    <span className="font-medium">Budget:</span> ${campaign.budget_usd}
                  </p>
                  {campaign.release_date && (
                    <p>
                      <span className="font-medium">Release:</span>{" "}
                      {formatDate(campaign.release_date)}
                    </p>
                  )}
                  <p>
                    <span className="font-medium">Created:</span>{" "}
                    {formatDate(campaign.created_at)}
                  </p>
                </div>
                <div className="mt-4 text-blue-600 hover:text-blue-700 font-medium">
                  View Details →
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
