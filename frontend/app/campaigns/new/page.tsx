"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface Song {
  song_id: string;
  title: string;
  artist_name: string | null;
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [songs, setSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    song_id: "",
    budget_usd: 500,
    release_date: "",
    campaign_duration_days: 28,
    target_audience: "",
    target_country: "US",
    preferred_platforms: ["Instagram", "TikTok", "YouTube", "Spotify"],
    audience_size: "",
    goals: [] as string[],
    marketing_mix_preference: "combination",
  });

  // Fetch songs
  useEffect(() => {
    const fetchSongs = async () => {
      try {
        const token = localStorage.getItem("api_token");
        if (!token) {
          setError("No API token found");
          setLoading(false);
          return;
        }

        const res = await fetch("/api/v1/songs", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          throw new Error("Failed to fetch songs");
        }

        const data = await res.json();
        setSongs(data.items || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error loading songs");
      } finally {
        setLoading(false);
      }
    };

    fetchSongs();
  }, []);

  const handlePlatformToggle = (platform: string) => {
    setFormData({
      ...formData,
      preferred_platforms: formData.preferred_platforms.includes(platform)
        ? formData.preferred_platforms.filter((p) => p !== platform)
        : [...formData.preferred_platforms, platform],
    });
  };

  const handleGoalToggle = (goal: string) => {
    setFormData({
      ...formData,
      goals: formData.goals.includes(goal)
        ? formData.goals.filter((g) => g !== goal)
        : [...formData.goals, goal],
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (!formData.song_id) {
        throw new Error("Please select a song");
      }

      if (formData.budget_usd < 100) {
        throw new Error("Budget must be at least $100");
      }

      const token = localStorage.getItem("api_token");
      if (!token) {
        throw new Error("No API token found");
      }

      const payload = {
        song_id: formData.song_id,
        budget_usd: formData.budget_usd,
        release_date: formData.release_date || null,
        campaign_duration_days: formData.campaign_duration_days,
        target_audience: formData.target_audience || null,
        target_country: formData.target_country,
        preferred_platforms: formData.preferred_platforms,
        audience_size: formData.audience_size ? parseInt(formData.audience_size) : null,
        goals: formData.goals,
        marketing_mix_preference: formData.marketing_mix_preference,
      };

      const res = await fetch("/api/v1/campaigns", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": `campaign-${Date.now()}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create campaign");
      }

      const data = await res.json();
      router.push(`/campaigns/${data.campaign_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p>Loading songs...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">New Marketing Campaign</h1>
          <Link href="/campaigns" className="text-blue-600 hover:underline">
            Back to Campaigns
          </Link>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {songs.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-6 text-center">
            <p className="text-gray-600 mb-4">
              You do not have any songs yet. Create a song first to start a campaign.
            </p>
            <Link href="/songs/new" className="text-blue-600 hover:underline font-medium">
              Create a Song
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-8">
            {/* Song Selection */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Song *
              </label>
              <select
                value={formData.song_id}
                onChange={(e) => setFormData({ ...formData, song_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">Select a song...</option>
                {songs.map((song) => (
                  <option key={song.song_id} value={song.song_id}>
                    {song.title} {song.artist_name && `- ${song.artist_name}`}
                  </option>
                ))}
              </select>
            </div>

            {/* Budget Slider */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Budget: ${formData.budget_usd}
              </label>
              <input
                type="range"
                min="100"
                max="5000"
                step="50"
                value={formData.budget_usd}
                onChange={(e) =>
                  setFormData({ ...formData, budget_usd: parseInt(e.target.value) })
                }
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>$100</span>
                <span>$5000</span>
              </div>
            </div>

            {/* Release Date */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Release Date (Optional)
              </label>
              <input
                type="date"
                value={formData.release_date}
                onChange={(e) =>
                  setFormData({ ...formData, release_date: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Campaign Duration */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Campaign Duration (days)
              </label>
              <input
                type="number"
                min="7"
                max="90"
                value={formData.campaign_duration_days}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    campaign_duration_days: parseInt(e.target.value),
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Target Audience */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Audience (Optional)
              </label>
              <textarea
                value={formData.target_audience}
                onChange={(e) =>
                  setFormData({ ...formData, target_audience: e.target.value })
                }
                placeholder="e.g., Fans of indie pop aged 18-35"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={2}
              />
            </div>

            {/* Target Country */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Country
              </label>
              <input
                type="text"
                value={formData.target_country}
                onChange={(e) =>
                  setFormData({ ...formData, target_country: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Preferred Platforms */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Preferred Platforms
              </label>
              <div className="space-y-2">
                {["Instagram", "TikTok", "YouTube", "Spotify"].map((platform) => (
                  <label key={platform} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.preferred_platforms.includes(platform)}
                      onChange={() => handlePlatformToggle(platform)}
                      className="mr-2"
                    />
                    <span className="text-sm">{platform}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Artist Audience Size */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Your Current Audience Size (Optional)
              </label>
              <input
                type="number"
                min="0"
                value={formData.audience_size}
                onChange={(e) =>
                  setFormData({ ...formData, audience_size: e.target.value })
                }
                placeholder="e.g., 10000"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Goals */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Campaign Goals
              </label>
              <div className="space-y-2">
                {[
                  "Build awareness",
                  "Increase streams",
                  "Gain followers",
                  "Generate engagement",
                ].map((goal) => (
                  <label key={goal} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.goals.includes(goal)}
                      onChange={() => handleGoalToggle(goal)}
                      className="mr-2"
                    />
                    <span className="text-sm">{goal}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Marketing Mix */}
            <div className="mb-8">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Marketing Mix Preference
              </label>
              <div className="space-y-2">
                {[
                  { value: "organic", label: "Organic promotion only" },
                  { value: "paid", label: "Paid ads only" },
                  { value: "influencer", label: "Influencer collaborations" },
                  { value: "combination", label: "Combination of all" },
                ].map((opt) => (
                  <label key={opt.value} className="flex items-center">
                    <input
                      type="radio"
                      name="marketing_mix"
                      value={opt.value}
                      checked={formData.marketing_mix_preference === opt.value}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          marketing_mix_preference: e.target.value,
                        })
                      }
                      className="mr-2"
                    />
                    <span className="text-sm">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-lg transition"
            >
              {submitting ? "Creating campaign..." : "Create Campaign"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
