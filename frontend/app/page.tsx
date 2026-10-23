"use client";

import {
  ArrowDownToLine,
  ArrowRight,
  AudioLines,
  Check,
  CircleAlert,
  CircleUserRound,
  FileAudio2,
  Headphones,
  KeyRound,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Music2,
  Plus,
  ShieldCheck,
  Sparkles,
  Upload,
  Video,
  WandSparkles,
  X,
} from "lucide-react";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiBaseUrl, apiRequest } from "@/lib/api";
import type {
  ARReport,
  AgentPipeline,
  AudienceHypotheses,
  ArtistProfile,
  ArtistProfilePayload,
  Capabilities,
  ConsentList,
  ConsentRecord,
  Intelligence,
  Job,
  OAuthStart,
  PlatformConnection,
  PlatformConnectionList,
  PlatformProvider,
  ReleasePlan,
  ReleasePlanList,
  Song,
  SongList,
  VideoRender,
  VideoRenderList,
} from "@/lib/contracts";

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

type Phase = "connect" | "onboarding" | "dashboard" | "studio" | "working" | "report";
type RightsBasis = "" | "owned" | "licensed" | "authorized";

const emptyProfile: ArtistProfilePayload = {
  display_name: "",
  bio: null,
  primary_genre: null,
  language: null,
  territories: [],
  goals: [],
  brand_voice: null,
};

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "AUTHENTICATION_REQUIRED" || error.code === "AUTH_CONFIGURATION_MISSING") {
      return "That studio key could not be verified. Check the key and try again.";
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export default function Home() {
  const [phase, setPhase] = useState<Phase>("connect");
  const [profile, setProfile] = useState<ArtistProfile | null>(null);
  const [profileDraft, setProfileDraft] = useState<ArtistProfilePayload>(emptyProfile);
  const [songs, setSongs] = useState<Song[]>([]);
  const [nextSongCursor, setNextSongCursor] = useState<string | null>(null);
  const [songCount, setSongCount] = useState(0);
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [platformConnections, setPlatformConnections] = useState<PlatformConnection[]>([]);
  const [connectionMessage, setConnectionMessage] = useState("");
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [songTitle, setSongTitle] = useState("");
  const [artistName, setArtistName] = useState("");
  const [lyricsDraft, setLyricsDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [recordingRightsBasis, setRecordingRightsBasis] = useState<RightsBasis>("");
  const [compositionRightsBasis, setCompositionRightsBasis] = useState<RightsBasis>("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [audioProcessingConsent, setAudioProcessingConsent] = useState(false);
  const [derivedAnalysisConsent, setDerivedAnalysisConsent] = useState(false);
  const [thirdPartyAiConsent, setThirdPartyAiConsent] = useState(false);
  const [song, setSong] = useState<Song | null>(null);
  const [intelligence, setIntelligence] = useState<Intelligence | null>(null);
  const [report, setReport] = useState<ARReport | null>(null);
  const [agentPipeline, setAgentPipeline] = useState<AgentPipeline | null>(null);
  const [agentPipelineBusy, setAgentPipelineBusy] = useState(false);
  const [agentPipelineError, setAgentPipelineError] = useState("");
  const [audienceHypotheses, setAudienceHypotheses] = useState<AudienceHypotheses | null>(null);
  const [releasePlans, setReleasePlans] = useState<ReleasePlan[]>([]);
  const [videoRenders, setVideoRenders] = useState<VideoRender[]>([]);
  const [sourceAssetId, setSourceAssetId] = useState<string | null>(null);
  const [releaseDateDraft, setReleaseDateDraft] = useState("");
  const [releaseGoalDraft, setReleaseGoalDraft] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities["capabilities"] | null>(null);
  const [statusText, setStatusText] = useState("Preparing your private workspace…");
  const [errorText, setErrorText] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [showToken, setShowToken] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const audioFeatures = useMemo(() => intelligence?.audio_features ?? {}, [intelligence]);
  const latestConsents = useMemo(() => {
    const seen = new Set<string>();
    return consents.filter((consent) => {
      const key = `${consent.consent_type}:${consent.song_id ?? "workspace"}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [consents]);
  const promotionalConsentActive = useMemo(() => {
    if (!song) return false;
    const scoped = latestConsents.find(
      (consent) => consent.consent_type === "promotional_asset_generation" && consent.song_id === song.song_id,
    );
    if (scoped) return scoped.granted;
    return latestConsents.some(
      (consent) => consent.consent_type === "promotional_asset_generation" && consent.song_id === null && consent.granted,
    );
  }, [latestConsents, song]);
  const platformConnectionConsentActive = useMemo(
    () => latestConsents.some(
      (consent) => consent.consent_type === "platform_account_connection" &&
        consent.song_id === null && consent.granted,
    ),
    [latestConsents],
  );

  const loadReport = useCallback(async (authToken: string, id: string) => {
    const [intel, arReport, audience, pipeline] = await Promise.all([
      apiRequest<Intelligence>(`/api/v1/analyses/${id}/intelligence`, authToken),
      apiRequest<ARReport>(`/api/v1/analyses/${id}/report`, authToken),
      apiRequest<AudienceHypotheses>(`/api/v1/analyses/${id}/audience-hypotheses`, authToken),
      apiRequest<AgentPipeline | null>(`/api/v1/analyses/${id}/agent-pipeline`, authToken),
    ]);
    setIntelligence(intel);
    setReport(arReport);
    setAudienceHypotheses(audience);
    setAgentPipeline(pipeline);
    const [plans, renders, assets] = await Promise.all([
      apiRequest<ReleasePlanList>(`/api/v1/songs/${intel.song_id}/release-plans`, authToken),
      apiRequest<VideoRenderList>(`/api/v1/songs/${intel.song_id}/video-renders`, authToken),
      apiRequest<{ items: Array<{ asset_id: string; asset_kind: string; status: string }> }>(
        `/api/v1/songs/${intel.song_id}/assets`,
        authToken,
      ),
    ]);
    setReleasePlans(plans.items);
    setVideoRenders(renders.items);
    setSourceAssetId(assets.items.find((asset) => asset.asset_kind === "audio_original" && asset.status === "ready")?.asset_id ?? null);
    sessionStorage.setItem("aimm:lastAnalysisId", id);
    setPhase("report");
  }, []);

  const verifySession = useCallback(async (authToken: string, restore: boolean) => {
    await apiRequest<{ authenticated: boolean }>("/api/v1/session", authToken);
    setToken(authToken);
    sessionStorage.setItem("aimm:studioToken", authToken);
    const [artistProfile, songPage, consentList] = await Promise.all([
      apiRequest<ArtistProfile | null>("/api/v1/artist/profile", authToken),
      apiRequest<SongList>("/api/v1/songs?limit=10", authToken),
      apiRequest<ConsentList>("/api/v1/consents", authToken),
    ]);
    const connectionList = await apiRequest<PlatformConnectionList>("/api/v1/connections", authToken);
    setProfile(artistProfile);
    setSongs(songPage.items);
    setNextSongCursor(songPage.next_cursor);
    setSongCount(songPage.total_count);
    setConsents(consentList.items);
    setPlatformConnections(connectionList.items);
    if (artistProfile) {
      setProfileDraft({
        display_name: artistProfile.display_name,
        bio: artistProfile.bio,
        primary_genre: artistProfile.primary_genre,
        language: artistProfile.language,
        territories: artistProfile.territories,
        goals: artistProfile.goals,
        brand_voice: artistProfile.brand_voice,
      });
    }
    setPhase(artistProfile ? "dashboard" : "onboarding");
    const capabilityResult = await fetch(`${apiBaseUrl()}/api/v1/capabilities`, { cache: "no-store" });
    if (capabilityResult.ok) {
      const result = await capabilityResult.json() as Capabilities;
      setCapabilities(result.capabilities);
    }
    if (!artistProfile) return;
    if (restore) {
      const savedSong = sessionStorage.getItem("aimm:lastSong");
      const savedAnalysis = sessionStorage.getItem("aimm:lastAnalysisId");
      if (savedSong) {
        const restoredSong = await apiRequest<Song>(`/api/v1/songs/${savedSong}`, authToken);
        setSong(restoredSong);
        setSongTitle(restoredSong.title);
        setArtistName(restoredSong.artist_name || "");
      }
      if (savedAnalysis) {
        const check = await apiRequest<{ status: string }>(`/api/v1/analyses/${savedAnalysis}`, authToken);
        if (check.status === "succeeded") {
          await loadReport(authToken, savedAnalysis);
        }
      }
    }
  }, [loadReport]);

  useEffect(() => {
    const savedToken = sessionStorage.getItem("aimm:studioToken");
    if (!savedToken) return;
    void verifySession(savedToken, true).catch(() => {
      sessionStorage.removeItem("aimm:studioToken");
      setToken("");
      setPhase("connect");
    });
  }, [verifySession]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("platform_connection");
    if (!result) return;
    const provider = params.get("provider") || "platform";
    const reason = params.get("reason");
    if (result === "connected") {
      setConnectionMessage(`${provider} account connected. Publishing remains disabled.`);
    } else {
      const safeReasons: Record<string, string> = {
        invalid_state: "The sign-in link expired or was already used. Start again.",
        authorization_denied: "The provider authorization was cancelled or denied.",
        consent_withdrawn: "Platform connection consent was withdrawn before the connection completed.",
        provider_timeout: "The provider took too long to respond. Try again.",
        provider_unavailable: "The provider could not be reached. Try again.",
        account_unavailable: "No eligible account was available for this provider.",
      };
      setConnectionMessage(safeReasons[reason || ""] || "The provider could not complete the connection. Check app configuration and try again.");
    }
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  useEffect(() => {
    const pending = videoRenders.find((render) => render.status === "queued" || render.status === "running");
    if (!token || !pending) return;
    const timeout = window.setTimeout(() => {
      void apiRequest<VideoRender>(pending.status_url, token)
        .then((updated) => setVideoRenders((current) => current.map(
          (render) => render.render_id === updated.render_id ? updated : render,
        )))
        .catch((error: unknown) => setErrorText(friendlyError(error)));
    }, 1200);
    return () => window.clearTimeout(timeout);
  }, [token, videoRenders]);

  const chooseFile = (file: File | undefined) => {
    setErrorText("");
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setSelectedFile(null);
      setErrorText("This file is larger than the 50 MB upload limit.");
      return;
    }
    setSelectedFile(file);
  };

  const connect = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText("");
    setBusy(true);
    try {
      await verifySession(tokenDraft.trim(), true);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const saveArtistProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText("");
    setBusy(true);
    try {
      const saved = await apiRequest<ArtistProfile>("/api/v1/artist/profile", token, {
        method: "PUT",
        body: JSON.stringify(profileDraft),
      });
      setProfile(saved);
      setProfileDraft({
        display_name: saved.display_name,
        bio: saved.bio,
        primary_genre: saved.primary_genre,
        language: saved.language,
        territories: saved.territories,
        goals: saved.goals,
        brand_voice: saved.brand_voice,
      });
      setPhase("dashboard");
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const loadMoreSongs = async () => {
    if (!token || !nextSongCursor || busy) return;
    setBusy(true);
    try {
      const query = new URLSearchParams({ limit: "10", cursor: nextSongCursor });
      const page = await apiRequest<SongList>(`/api/v1/songs?${query.toString()}`, token);
      setSongs((current) => [...current, ...page.items]);
      setNextSongCursor(page.next_cursor);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const withdrawConsent = async (consentId: string) => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const withdrawal = await apiRequest<ConsentRecord>(
        `/api/v1/consents/${consentId}/withdraw`,
        token,
        { method: "POST" },
      );
      setConsents((current) => [withdrawal, ...current]);
      if (withdrawal.consent_type === "platform_account_connection") {
        const connections = await apiRequest<PlatformConnectionList>("/api/v1/connections", token);
        setPlatformConnections(connections.items);
      }
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const pollJob = async (jobId: string, authToken: string, label: string): Promise<Job> => {
    for (let attempt = 0; attempt < 360; attempt += 1) {
      const job = await apiRequest<Job>(`/api/v1/jobs/${jobId}`, authToken);
      if (job.status === "succeeded") return job;
      if (job.status === "failed") {
        throw new ApiError(job.error?.message || "The analysis job failed.", job.error?.code);
      }
      setStatusText(`${label}${job.stage ? ` · ${job.stage.replaceAll("_", " ")}` : ""}`);
      await sleep(1500);
    }
    throw new ApiError("This job is taking longer than expected. Your private job is still saved; reconnect to check it.");
  };

  const startAnalysis = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedFile) return;
    if (!songTitle.trim()) {
      setErrorText("Give this track a title before uploading.");
      return;
    }
    if (!recordingRightsBasis || !compositionRightsBasis || !rightsConfirmed || !audioProcessingConsent || !derivedAnalysisConsent) {
      setErrorText("Declare both rights bases and give separate processing and analysis-storage consent before uploading.");
      return;
    }
    setErrorText("");
    setBusy(true);
    setPhase("working");
    try {
      setStatusText("Creating your private track space…");
      const createdSong = await apiRequest<Song>("/api/v1/songs", token, {
        method: "POST",
        body: JSON.stringify({
          title: songTitle.trim(),
          artist_name: artistName.trim() || null,
          genre_preferences: [],
        }),
      });
      setSong(createdSong);
      setSongs((current) => [createdSong, ...current.filter((item) => item.song_id !== createdSong.song_id)]);
      setSongCount((current) => current + 1);
      sessionStorage.setItem("aimm:lastSong", createdSong.song_id);
      const processingConsent = await apiRequest<ConsentRecord>("/api/v1/consents", token, {
        method: "POST",
        body: JSON.stringify({ consent_type: "audio_processing", song_id: createdSong.song_id }),
      });
      setConsents((current) => [processingConsent, ...current]);
      const analysisStorageConsent = await apiRequest<ConsentRecord>("/api/v1/consents", token, {
        method: "POST",
        body: JSON.stringify({ consent_type: "derived_analysis_storage", song_id: createdSong.song_id }),
      });
      setConsents((current) => [analysisStorageConsent, ...current]);
      await apiRequest("/api/v1/rights/declarations", token, {
        method: "POST",
        body: JSON.stringify({
          song_id: createdSong.song_id,
          recording_rights_basis: recordingRightsBasis,
          composition_rights_basis: compositionRightsBasis,
          rights_confirmed: true,
        }),
      });
      if (thirdPartyAiConsent) {
        const aiConsent = await apiRequest<ConsentRecord>("/api/v1/consents", token, {
          method: "POST",
          body: JSON.stringify({ consent_type: "third_party_ai", song_id: createdSong.song_id }),
        });
        setConsents((current) => [aiConsent, ...current]);
      }
      setStatusText("Preparing a private upload…");
      const intent = await apiRequest<{
        asset_id: string;
        upload_method: "PUT";
        upload_url: string;
      }>(`/api/v1/songs/${createdSong.song_id}/assets/upload-intent`, token, {
        method: "POST",
        body: JSON.stringify({
          filename: selectedFile.name,
          declared_content_type: selectedFile.type || "application/octet-stream",
          size_bytes: selectedFile.size,
          asset_kind: "audio_original",
        }),
      });
      setStatusText("Uploading privately…");
      const upload = await fetch(intent.upload_url, {
        method: intent.upload_method,
        headers: { Authorization: `Bearer ${token}`, "Content-Type": selectedFile.type || "application/octet-stream" },
        body: selectedFile,
      });
      if (!upload.ok) {
        const details = await upload.json().catch(() => null) as { error?: { message?: string } } | null;
        throw new ApiError(details?.error?.message || `Private upload failed (${upload.status}).`);
      }
      setStatusText("Checking that your audio is decodable…");
      const verification = await apiRequest<{ job_id: string }>(
        `/api/v1/songs/${createdSong.song_id}/assets/complete`,
        token,
        { method: "POST", body: JSON.stringify({ asset_id: intent.asset_id }) },
      );
      await pollJob(verification.job_id, token, "Validating audio");

      setStatusText("Building measured Song Intelligence…");
      const accepted = await apiRequest<{
        analysis_id: string;
        job_id: string;
      }>(`/api/v1/songs/${createdSong.song_id}/analyses`, token, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          asset_id: intent.asset_id,
          analysis_profile: "standard_v1",
          include_pretrained_predictions: false,
          generate_ai_report: true,
          allow_third_party_ai: thirdPartyAiConsent,
          lyrics: lyricsDraft.trim() || null,
        }),
      });
      setSourceAssetId(intent.asset_id);
      sessionStorage.setItem("aimm:lastAnalysisId", accepted.analysis_id);
      await pollJob(accepted.job_id, token, "Analyzing track");
      setStatusText("Opening your A&R notes…");
      await loadReport(token, accepted.analysis_id);
      setSelectedFile(null);
      setRecordingRightsBasis("");
      setCompositionRightsBasis("");
      setLyricsDraft("");
      setRightsConfirmed(false);
      setAudioProcessingConsent(false);
      setDerivedAnalysisConsent(false);
      setThirdPartyAiConsent(false);
    } catch (error) {
      setErrorText(friendlyError(error));
      setPhase(song ? "studio" : "studio");
    } finally {
      setBusy(false);
    }
  };

  const startFresh = () => {
    setReport(null);
    setAgentPipeline(null);
    setAgentPipelineError("");
    setAudienceHypotheses(null);
    setReleasePlans([]);
    setVideoRenders([]);
    setSourceAssetId(null);
    setReleaseDateDraft("");
    setReleaseGoalDraft("");
    setIntelligence(null);
    setSong(null);
    setSongTitle("");
    setArtistName("");
    setLyricsDraft("");
    setSelectedFile(null);
    sessionStorage.removeItem("aimm:lastSong");
    sessionStorage.removeItem("aimm:lastAnalysisId");
    setErrorText("");
    setPhase("studio");
  };

  const disconnect = () => {
    sessionStorage.removeItem("aimm:studioToken");
    setToken("");
    setTokenDraft("");
    setPhase("connect");
    setReport(null);
    setAgentPipeline(null);
    setAgentPipelineError("");
    setAudienceHypotheses(null);
    setReleasePlans([]);
    setVideoRenders([]);
    setSourceAssetId(null);
    setIntelligence(null);
    setProfile(null);
    setSongs([]);
    setConsents([]);
    setPlatformConnections([]);
    setConnectionMessage("");
  };

  const runAgentPipeline = async () => {
    if (!token || !intelligence || agentPipelineBusy) return;
    setAgentPipelineBusy(true);
    setAgentPipelineError("");
    try {
      const result = await apiRequest<AgentPipeline>(
        `/api/v1/analyses/${intelligence.analysis_id}/agent-pipeline`,
        token,
        { method: "POST" },
      );
      setAgentPipeline(result);
    } catch (error) {
      setAgentPipelineError(friendlyError(error));
    } finally {
      setAgentPipelineBusy(false);
    }
  };

  const grantPlatformConnectionConsent = async () => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const consent = await apiRequest<ConsentRecord>("/api/v1/consents", token, {
        method: "POST",
        body: JSON.stringify({ consent_type: "platform_account_connection" }),
      });
      setConsents((current) => [consent, ...current]);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const startPlatformConnection = async (provider: PlatformProvider) => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const start = await apiRequest<OAuthStart>(`/api/v1/connections/${provider}/oauth/start`, token, {
        method: "POST",
      });
      window.location.assign(start.authorization_url);
    } catch (error) {
      setErrorText(friendlyError(error));
      setBusy(false);
    }
  };

  const disconnectPlatform = async (provider: PlatformProvider) => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      await apiRequest<void>(`/api/v1/connections/${provider}`, token, { method: "DELETE" });
      const connections = await apiRequest<PlatformConnectionList>("/api/v1/connections", token);
      setPlatformConnections(connections.items);
      setConnectionMessage(`${provider} credentials were removed from this workspace. Revoke the app in the provider's security settings to invalidate the provider-side grant too.`);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const createReleasePlan = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !song || !intelligence || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const plan = await apiRequest<ReleasePlan>("/api/v1/release-plans", token, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          song_id: song.song_id,
          analysis_id: intelligence.analysis_id,
          release_date: releaseDateDraft || null,
          goal: releaseGoalDraft.trim() || null,
        }),
      });
      setReleasePlans((current) => [plan, ...current.filter((item) => item.plan_id !== plan.plan_id)]);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const approveReleasePlan = async (planId: string) => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const plan = await apiRequest<ReleasePlan>(`/api/v1/release-plans/${planId}/approve`, token, {
        method: "POST",
      });
      setReleasePlans((current) => current.map((item) => item.plan_id === plan.plan_id ? plan : item));
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const grantPromotionalConsent = async () => {
    if (!token || !song || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const consent = await apiRequest<ConsentRecord>("/api/v1/consents", token, {
        method: "POST",
        body: JSON.stringify({
          consent_type: "promotional_asset_generation",
          song_id: song.song_id,
        }),
      });
      setConsents((current) => [consent, ...current]);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const createVideoRender = async (renderFormat: VideoRender["render_format"]) => {
    if (!token || !song || !sourceAssetId || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const render = await apiRequest<VideoRender>(`/api/v1/songs/${song.song_id}/video-renders`, token, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ asset_id: sourceAssetId, render_format: renderFormat }),
      });
      setVideoRenders((current) => [render, ...current.filter((item) => item.render_id !== render.render_id)]);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const downloadVideoRender = async (render: VideoRender) => {
    if (!token || !song || !render.download_url || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const response = await fetch(`${apiBaseUrl()}${render.download_url}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as
          | { error?: { code?: string; message?: string } }
          | null;
        throw new ApiError(body?.error?.message || `Download failed (${response.status}).`, body?.error?.code);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `${song.title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${render.render_format}.mp4`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (error) {
      setErrorText(friendlyError(error));
    } finally {
      setBusy(false);
    }
  };

  const publishYouTube = async (render: VideoRender) => {
    if (!token || busy) return;
    setBusy(true);
    setErrorText("");
    try {
      const job = await apiRequest<{ job_id: string }>(`/api/v1/video/${render.render_id}/publish-youtube`, token, {
        method: "POST",
      });
      // Show success message
      setErrorText(""); // Clear any previous errors
      const successMsg = `✓ Video publishing queued to YouTube (Job: ${job.job_id})`;
      setConnectionMessage(successMsg);
      console.log("YouTube publish success:", successMsg);
      // Clear message after 10 seconds
      setTimeout(() => setConnectionMessage(""), 10000);
    } catch (error) {
      const errorMsg = friendlyError(error);
      console.error("YouTube publish error:", errorMsg);
      setErrorText(errorMsg);
    } finally {
      setBusy(false);
    }
  };

  const downloadReport = () => {
    if (!report) return;
    const file = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const objectUrl = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `${(song?.title || "song-intelligence").toLowerCase().replace(/[^a-z0-9]+/g, "-")}-ar-report.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  };

  const connectView = (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-8 py-16">
      <div className="noise-grid pointer-events-none absolute inset-0 opacity-30" />
      <div className="absolute -left-36 top-20 h-96 w-96 rounded-full bg-[#d7fb58]/[0.06] blur-[100px]" />
      <div className="relative grid w-full max-w-6xl grid-cols-[1.1fr_.9fr] items-center gap-20">
        <section>
          <Brand />
          <p className="mt-20 text-xs font-semibold uppercase tracking-[.24em] text-[#d7fb58]">A quieter kind of music intelligence</p>
          <h1 className="mt-5 max-w-xl text-6xl font-semibold leading-[1.02] tracking-[-.055em] text-[#f2f3eb]">
            Hear what&apos;s<br />already <span className="font-serif italic text-[#d7fb58]">there.</span>
          </h1>
          <p className="mt-7 max-w-lg text-base leading-7 text-[#a1a9a5]">
            Private, evidence-grounded notes for the music you&apos;re making. Upload a track, see what can actually be measured, and decide what to do next.
          </p>
          <div className="mt-12 flex items-center gap-3 text-xs text-[#a1a9a5]">
            <ShieldCheck size={16} className="text-[#d7fb58]" />
            <span>Your audio stays in your private local studio.</span>
          </div>
        </section>
        <section className="soft-shadow rounded-3xl border border-[#343a3d] bg-[#181b1e] p-8">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-[.17em] text-[#a1a9a5]">Studio access</span>
            <span className="flex items-center gap-2 rounded-full border border-[#343a3d] px-3 py-1.5 text-[11px] text-[#a1a9a5]"><LockKeyhole size={12} /> PRIVATE</span>
          </div>
          <h2 className="mt-8 text-2xl font-semibold tracking-tight">Connect your workspace</h2>
          <p className="mt-2 text-sm leading-6 text-[#a1a9a5]">Enter the local studio key configured by the person running this app. It is held only for this browser session.</p>
          <form onSubmit={connect} className="mt-8">
            <label htmlFor="studio-key" className="mb-2 block text-xs font-medium text-[#d3d8d2]">Studio key</label>
            <div className="flex items-center rounded-xl border border-[#454c4e] bg-[#101214] px-3 transition focus-within:border-[#d7fb58]">
              <KeyRound size={16} className="shrink-0 text-[#89918c]" />
              <input
                id="studio-key"
                autoComplete="off"
                type={showToken ? "text" : "password"}
                value={tokenDraft}
                onChange={(event) => setTokenDraft(event.target.value)}
                placeholder="Paste your studio key"
                required
                className="min-w-0 flex-1 bg-transparent px-3 py-4 text-sm text-[#f2f3eb] outline-none placeholder:text-[#8e9790]"
              />
              <button type="button" onClick={() => setShowToken((value) => !value)} className="px-2 py-2 text-xs text-[#a1a9a5] hover:text-white" aria-label={showToken ? "Hide studio key" : "Show studio key"}>
                {showToken ? "Hide" : "Show"}
              </button>
            </div>
            {errorText && <p role="alert" className="mt-3 text-sm text-[#ff9a7d]">{errorText}</p>}
            <button disabled={busy} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#d7fb58] px-5 py-4 text-sm font-semibold text-[#151813] transition hover:bg-[#e4ff86] disabled:cursor-wait disabled:opacity-70">
              {busy ? <LoaderCircle size={17} className="animate-spin" /> : <>Enter the studio <ArrowRight size={16} /></>}
            </button>
          </form>
          <div className="mt-8 border-t border-[#343a3d] pt-5 text-xs leading-5 text-[#818a84]">
            Need a key? Set <code className="rounded bg-[#24292b] px-1.5 py-0.5 text-[#d7fb58]">APP_API_TOKEN</code> in the backend&apos;s local <code>.env</code> file.
          </div>
        </section>
      </div>
    </main>
  );

  if (phase === "connect") return connectView;

  return (
    <div className="min-h-screen bg-[#101214]">
      <aside className="fixed inset-y-0 left-0 z-10 hidden w-[244px] flex-col border-r border-[#292e31] bg-[#131618] px-5 py-6 xl:flex">
        <Brand compact />
        <div className="mt-14 px-3 text-[10px] font-semibold uppercase tracking-[.19em] text-[#8e9790]">Workspace</div>
        <nav className="mt-3 space-y-1" aria-label="Workspace navigation">
          <button disabled={!profile} onClick={() => setPhase("dashboard")} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm disabled:cursor-not-allowed disabled:opacity-50 ${phase === "dashboard" ? "bg-[#242a25] font-medium text-[#eaf0df]" : "text-[#a1a9a5] hover:bg-[#1d2222]"}`}>
            <LayoutDashboard size={17} className={phase === "dashboard" ? "text-[#d7fb58]" : ""} /> Dashboard
          </button>
          <button disabled={!profile} onClick={() => setPhase("studio")} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm disabled:cursor-not-allowed disabled:opacity-50 ${phase === "studio" ? "bg-[#242a25] font-medium text-[#eaf0df]" : "text-[#a1a9a5] hover:bg-[#1d2222]"}`}>
            <AudioLines size={17} className={phase === "studio" ? "text-[#d7fb58]" : ""} /> Song intelligence
          </button>
          <div className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm text-[#8e9790]">
            <Music2 size={17} /> Release workspace <span className="ml-auto rounded-full bg-[#24282a] px-2 py-0.5 text-[9px] uppercase tracking-wider">Soon</span>
          </div>
        </nav>
        <div className="mt-auto rounded-2xl border border-[#343a3d] bg-[#191d1f] p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-[#dfe4d9]"><ShieldCheck size={15} className="text-[#d7fb58]" /> Private by default</div>
          <p className="mt-2 text-[11px] leading-5 text-[#929a94]">No publishing or ads. Social profiles connect only with separate read-only consent.</p>
        </div>
        <button onClick={disconnect} className="mt-4 flex items-center gap-2 px-3 py-2 text-xs text-[#929a94] hover:text-white"><X size={14} /> Lock studio</button>
      </aside>

      <div className="xl:pl-[244px]">
        <header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b border-[#292e31] bg-[#101214]/90 px-6 backdrop-blur-xl lg:px-10">
          <div className="flex items-center gap-2 text-xs text-[#818a84]"><span>Studio</span><span className="text-[#4a514d]">/</span><span className="text-[#e3e7df]">{phase === "dashboard" ? "Dashboard" : phase === "onboarding" ? "Artist profile" : "Song intelligence"}</span></div>
          <div className="flex items-center gap-4">
            <span className="hidden items-center gap-2 rounded-full border border-[#353a3b] px-3 py-1.5 text-[10px] font-medium text-[#b5bcb6] sm:flex"><span className="h-1.5 w-1.5 rounded-full bg-[#d7fb58]" /> LOCAL WORKSPACE</span>
            {profile && <button onClick={() => setPhase("dashboard")} className="text-xs text-[#a1a9a5] hover:text-[#d7fb58]">Dashboard</button>}
            <button onClick={disconnect} className="flex h-8 w-8 items-center justify-center rounded-full border border-[#3a4042] text-xs font-semibold text-[#d7fb58]" aria-label="Lock studio">AM</button>
          </div>
        </header>

        <main className="mx-auto max-w-[1400px] px-6 py-9 lg:px-10 lg:py-12">
          {phase === "working" ? (
            <section className="mx-auto grid min-h-[68vh] max-w-2xl place-items-center text-center">
              <div>
                <div className="mx-auto grid h-24 w-24 place-items-center rounded-full border border-[#434a42] bg-[#1b201a] text-[#d7fb58]">
                  <AudioLines size={34} className="animate-pulse" />
                </div>
                <p className="mt-9 text-xs font-semibold uppercase tracking-[.2em] text-[#d7fb58]">Listening carefully</p>
                <h1 className="mt-4 text-4xl font-semibold tracking-[-.04em]">{songTitle || "Your track"} is in the studio.</h1>
                <p aria-live="polite" className="mt-4 text-sm text-[#a1a9a5]">{statusText}</p>
                <div className="mx-auto mt-8 h-1 w-64 overflow-hidden rounded-full bg-[#343a3d]">
                  <div className="h-full w-2/3 animate-pulse rounded-full bg-[#d7fb58]" />
                </div>
                <p className="mt-8 text-xs text-[#7f8782]">Audio is decoded locally. This can take a minute for longer tracks.</p>
              </div>
            </section>
          ) : phase === "report" && report && intelligence ? (
            <section>
              <div className="flex flex-wrap items-end justify-between gap-6">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-[#d7fb58]"><Sparkles size={14} /> Song Intelligence · v{intelligence.schema_version}</div>
                  <h1 className="mt-4 text-4xl font-semibold tracking-[-.045em] lg:text-5xl">{song?.title || songTitle}</h1>
                  <p className="mt-2 text-sm text-[#a1a9a5]">{song?.artist_name || artistName || "Independent artist"} <span className="mx-2 text-[#4c5350]">/</span> {new Date(report.created_at).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}</p>
                </div>
                <button onClick={startFresh} className="flex items-center gap-2 rounded-xl border border-[#454c4e] px-4 py-3 text-sm font-medium text-[#e3e7df] hover:border-[#d7fb58]"><Plus size={16} /> Analyze another track</button>
              </div>

              <div className="mt-9 grid gap-5 xl:grid-cols-[1.6fr_1fr]">
                <article className="rounded-3xl border border-[#3d433c] bg-[#1b201a] p-7 lg:p-9">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]"><WandSparkles size={15} /> A&R listening notes</div>
                    <span className="rounded-full border border-[#48503e] px-3 py-1.5 text-[10px] uppercase tracking-wider text-[#bdc8a8]">{report.provider === "mock" ? "Offline demo report" : `Generated with ${report.provider}`}</span>
                  </div>
                  <p className="mt-6 max-w-3xl text-xl leading-8 text-[#f0f1e9]">{report.summary}</p>
                  <div className="mt-8 grid gap-6 border-t border-[#3a4137] pt-6 md:grid-cols-2">
                    <ClaimList title="What the evidence supports" claims={[...report.strengths, ...report.improvement_opportunities]} />
                    <ClaimList title="Ideas to explore" claims={report.recommendations} />
                  </div>
                  <div className="mt-8 rounded-2xl border border-[#3a4137] bg-[#151915] p-5">
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.14em] text-[#c2c9bb]"><CircleAlert size={14} className="text-[#ff9a7d]" /> Read the limits</div>
                    <ul className="mt-3 space-y-2 text-xs leading-5 text-[#aab1a6]">
                      {report.limitations.map((item, index) => <li key={`${item}-${index}`} className="flex gap-2"><span className="text-[#a1a9a5]">—</span>{item}</li>)}
                    </ul>
                  </div>
                </article>

                <aside className="rounded-3xl border border-[#343a3d] bg-[#181b1e] p-7">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[.16em] text-[#a3aaa4]">Signal check</div>
                      <h2 className="mt-2 text-lg font-semibold">Measured, not imagined.</h2>
                    </div>
                    <Headphones size={20} className="text-[#d7fb58]" />
                  </div>
                    <div className="mt-7 space-y-3">
                      {Object.entries(audioFeatures).map(([key, feature]) => (
                        <FeatureTile
                          key={key}
                          id={`feature-${key}`}
                          label={featureLabel(key)}
                          feature={feature}
                          display={featureDisplay(key, feature)}
                        />
                      ))}
                    </div>
                  <p className="mt-5 border-t border-[#343a3d] pt-4 text-[11px] leading-5 text-[#929a94]">Estimates can be wrong. Check the source label and limitations before using a value in release materials.</p>
                </aside>
              </div>

              {intelligence.lyrics_analysis.available && (
                <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Artist-supplied lyrics</p>
                  <h2 className="mt-2 text-xl font-semibold">Text observations, not audience predictions.</h2>
                  {intelligence.lyrics_analysis.themes.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {intelligence.lyrics_analysis.themes.map((theme) => <span key={theme} className="rounded-full border border-[#454c4e] px-3 py-1.5 text-xs text-[#c4cbc4]">{theme}</span>)}
                    </div>
                  ) : <p className="mt-4 text-sm text-[#929a94]">No supported keyword theme was detected.</p>}
                  {intelligence.lyrics_analysis.candidate_lines.length > 0 ? (
                    <ul className="mt-5 space-y-3">
                      {intelligence.lyrics_analysis.candidate_lines.map((line, index) => (
                        <li key={`${line.text}-${index}`} className="rounded-xl border border-[#343a3d] bg-[#141719] p-4">
                          <p className="text-sm text-[#e3e7df]">“{line.text}”</p>
                          <p className="mt-2 text-[11px] leading-5 text-[#929a94]">{line.evidence}</p>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-4 text-sm text-[#929a94]">No repeated lyric lines were found.</p>}
                  <p className="mt-5 border-t border-[#343a3d] pt-4 text-[11px] leading-5 text-[#87908a]">{intelligence.lyrics_analysis.reason}</p>
                </section>
              )}
              {intelligence.sections.length > 0 && (
                <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Neutral audio segments</p>
                  <h2 className="mt-2 text-xl font-semibold">Silence-separated candidates</h2>
                  <ul className="mt-5 grid gap-3 md:grid-cols-2">
                    {intelligence.sections.map((section, index) => (
                      <li key={`${section.start_seconds}-${index}`} className="rounded-xl border border-[#343a3d] bg-[#141719] p-4">
                        <p className="text-sm font-medium text-[#e3e7df]">{formatDuration(section.start_seconds)}–{formatDuration(section.end_seconds)}</p>
                        <p className="mt-2 text-[11px] leading-5 text-[#929a94]">{section.evidence}</p>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-5 border-t border-[#343a3d] pt-4 text-[11px] leading-5 text-[#87908a]">These candidates do not label verse, chorus, or hook, and gaps can be missed when the recording has continuous background sound.</p>
                </section>
              )}
              {audienceHypotheses && (
                <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Audience intelligence</p>
                  <h2 className="mt-2 text-xl font-semibold">Hypotheses to test, never demographic facts.</h2>
                  {audienceHypotheses.hypotheses.length > 0 ? (
                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                      {audienceHypotheses.hypotheses.map((hypothesis, index) => (
                        <article key={`${hypothesis.statement}-${index}`} className="rounded-xl border border-[#343a3d] bg-[#141719] p-4">
                          <h3 className="text-sm font-medium text-[#e3e7df]">{hypothesis.statement}</h3>
                          <p className="mt-3 text-[11px] leading-5 text-[#b8c0b8]"><strong className="font-medium text-[#d7fb58]">Evidence:</strong> {hypothesis.evidence.map((item) => item.observation).join(" ")}</p>
                          {hypothesis.artist_context.length > 0 && <p className="mt-2 text-[11px] leading-5 text-[#929a94]">{hypothesis.artist_context.join(" · ")}</p>}
                          <p className="mt-3 text-[11px] leading-5 text-[#ffbd9f]">{hypothesis.uncertainty}</p>
                          <p className="mt-3 border-t border-[#343a3d] pt-3 text-[11px] leading-5 text-[#929a94]"><strong className="font-medium text-[#d3d8d2]">Possible experiment:</strong> {hypothesis.validation_experiment}</p>
                        </article>
                      ))}
                    </div>
                  ) : <p className="mt-4 text-sm text-[#929a94]">There is not enough song-specific evidence to suggest an audience hypothesis yet.</p>}
                  <ul className="mt-5 space-y-1 border-t border-[#343a3d] pt-4 text-[10px] leading-5 text-[#87908a]">
                    {audienceHypotheses.limitations.map((item) => <li key={item}>— {item}</li>)}
                  </ul>
                </section>
              )}
              <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Five-agent pipeline</p>
                    <h2 className="mt-2 text-xl font-semibold">Run all five agents on this track.</h2>
                    <p className="mt-2 max-w-3xl text-xs leading-5 text-[#929a94]">Music analysis feeds audience and content planning; those results feed marketing strategy; analytics then evaluates the full bundle. Results are saved with this analysis.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void runAgentPipeline()}
                    disabled={agentPipelineBusy || !intelligence}
                    className="flex items-center gap-2 rounded-xl bg-[#d7fb58] px-4 py-3 text-xs font-semibold text-[#151813] disabled:cursor-wait disabled:opacity-50"
                  >
                    {agentPipelineBusy ? <LoaderCircle size={15} className="animate-spin" /> : <Sparkles size={15} />}
                    {agentPipelineBusy ? "Running agents…" : agentPipeline ? "Run again" : "Run agent pipeline"}
                  </button>
                </div>
                <div className="mt-5 rounded-2xl border border-[#66503c] bg-[#211b16] p-4 text-[11px] leading-5 text-[#e1c3a7]">
                  This is a deterministic legacy pipeline, not autonomous AI. Audience matches are generic heuristics; campaign metrics are simulated. Marketing suggestions and budget percentages are drafts only—nothing is published, purchased, or executed.
                </div>
                {agentPipelineError && <p role="alert" className="mt-4 text-xs text-[#ff9a7d]">{agentPipelineError}</p>}
                {agentPipeline && (
                  <div className="mt-5 space-y-5">
                    <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold text-[#e3e7df]">Orchestrator summary</h3>
                        <span className="text-[10px] text-[#929a94]">Saved {new Date(agentPipeline.generated_at).toLocaleString()}</span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[#c7cec6]">{agentPipeline.results.final.orchestrator_summary}</p>
                      <ol className="mt-4 grid gap-2 md:grid-cols-2">
                        {agentPipeline.results.final.top_priority_actions.map((action, index) => (
                          <li key={`${action}-${index}`} className="rounded-lg border border-[#343a3d] p-3 text-xs leading-5 text-[#b9c1b8]">{index + 1}. {action}</li>
                        ))}
                      </ol>
                    </article>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                        <h3 className="text-sm font-semibold text-[#e3e7df]">1 · Music Analysis</h3>
                        <p className="mt-2 text-xs text-[#aab2aa]">{agentPipeline.results.song_intelligence.bpm} BPM · {agentPipeline.results.song_intelligence.musical_key} · {agentPipeline.results.song_intelligence.mood}</p>
                        <p className="mt-2 text-xs leading-5 text-[#929a94]">Hooks: {agentPipeline.results.song_intelligence.hooks.join(" · ")}</p>
                        <p className="mt-2 text-xs leading-5 text-[#929a94]">Themes: {agentPipeline.results.song_intelligence.lyrical_themes.join(", ")}</p>
                      </article>
                      <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                        <h3 className="text-sm font-semibold text-[#e3e7df]">2 · Audience Intelligence</h3>
                        <p className="mt-2 text-xs text-[#aab2aa]">Primary heuristic match: {agentPipeline.results.audience.primary_segment}</p>
                        <ul className="mt-3 space-y-2">
                          {agentPipeline.results.audience.segments.slice(0, 3).map((segment) => (
                            <li key={segment.name} className="flex items-center justify-between gap-3 text-xs text-[#929a94]">
                              <span>{segment.name}</span><span>{Math.round(segment.match_score * 100)}% match</span>
                            </li>
                          ))}
                        </ul>
                      </article>
                    </div>

                    <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                      <h3 className="text-sm font-semibold text-[#e3e7df]">3 · Content Strategy</h3>
                      <p className="mt-2 text-xs leading-5 text-[#929a94]">{agentPipeline.results.content_plan.overarching_angle}</p>
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        {agentPipeline.results.content_plan.pieces.map((piece, index) => (
                          <div key={`${piece.format}-${index}`} className="rounded-xl border border-[#343a3d] p-4">
                            <p className="text-xs font-medium text-[#d7fb58]">{piece.format}</p>
                            <p className="mt-2 text-xs font-medium text-[#e3e7df]">{piece.hook}</p>
                            <p className="mt-2 text-[11px] leading-5 text-[#929a94]">{piece.concept}</p>
                            <p className="mt-2 text-[11px] leading-5 text-[#aab2aa]">CTA: {piece.cta}</p>
                          </div>
                        ))}
                      </div>
                      <p className="mt-4 text-[11px] leading-5 text-[#929a94]">Suggested cadence: {agentPipeline.results.content_plan.posting_cadence}</p>
                    </article>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                        <h3 className="text-sm font-semibold text-[#e3e7df]">4 · Marketing Strategy</h3>
                        <p className="mt-2 text-xs leading-5 text-[#929a94]">{agentPipeline.results.marketing_strategy.key_message}</p>
                        <div className="mt-4 space-y-3">
                          {Object.entries(agentPipeline.results.marketing_strategy.phases).map(([phaseName, actions]) => (
                            <div key={phaseName}>
                              <p className="text-xs font-medium text-[#d7fb58]">{phaseName}</p>
                              <ul className="mt-1 space-y-1 text-[11px] leading-5 text-[#aab2aa]">
                                {actions.map((action) => <li key={action}>— {action}</li>)}
                              </ul>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 text-[11px] leading-5 text-[#929a94]">Draft platform priorities: {agentPipeline.results.marketing_strategy.platform_priority.join(", ")}</p>
                      </article>
                      <article className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                        <h3 className="text-sm font-semibold text-[#e3e7df]">5 · Analytics & Optimization</h3>
                        <p className="mt-1 text-[10px] uppercase tracking-wider text-[#ffbd9f]">Simulated—not measured campaign results</p>
                        <div className="mt-4 grid grid-cols-2 gap-3">
                          {[
                            ["Streams", agentPipeline.results.optimization.metrics.streams],
                            ["Saves", agentPipeline.results.optimization.metrics.saves],
                            ["Playlist adds", agentPipeline.results.optimization.metrics.playlist_adds],
                            ["Social views", agentPipeline.results.optimization.metrics.social_views],
                            ["Engagement", `${(agentPipeline.results.optimization.metrics.engagement_rate * 100).toFixed(1)}%`],
                            ["Score", `${agentPipeline.results.optimization.metrics.score}/100`],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-lg border border-[#343a3d] p-3">
                              <p className="text-[10px] text-[#929a94]">{label}</p>
                              <p className="mt-1 text-sm font-semibold text-[#e3e7df]">{typeof value === "number" ? value.toLocaleString() : value}</p>
                            </div>
                          ))}
                        </div>
                        <ul className="mt-4 space-y-2 text-[11px] leading-5 text-[#aab2aa]">
                          {agentPipeline.results.optimization.recommendations.map((item) => <li key={item}>— {item}</li>)}
                        </ul>
                      </article>
                    </div>

                    <details className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                      <summary className="cursor-pointer text-xs font-medium text-[#c7cec6]">View agent handoffs and run log</summary>
                      <ol className="mt-3 space-y-1 text-[10px] leading-5 text-[#929a94]">
                        {agentPipeline.results.logs.map((entry, index) => <li key={`${entry}-${index}`}>{entry}</li>)}
                      </ol>
                    </details>
                    <ul className="space-y-1 border-t border-[#343a3d] pt-4 text-[10px] leading-5 text-[#87908a]">
                      {agentPipeline.limitations.map((item) => <li key={item}>— {item}</li>)}
                    </ul>
                  </div>
                )}
              </section>
              <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Release planner</p>
                    <h2 className="mt-2 text-xl font-semibold">Turn a goal into a draft calendar.</h2>
                    <p className="mt-2 max-w-2xl text-xs leading-5 text-[#929a94]">The plan is an organic-first checklist. Approval does not publish, connect accounts, contact distributors, or spend money.</p>
                  </div>
                </div>
                {errorText && <p role="alert" className="mt-4 text-xs text-[#ff9a7d]">{errorText}</p>}
                <form onSubmit={createReleasePlan} className="mt-5 grid gap-4 rounded-2xl border border-[#343a3d] bg-[#141719] p-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
                  <label className="text-[11px] font-medium text-[#d3d8d2]">Target release date <span className="font-normal text-[#87908a]">optional</span>
                    <input type="date" value={releaseDateDraft} onChange={(event) => setReleaseDateDraft(event.target.value)} className="mt-2 w-full rounded-lg border border-[#454c4e] bg-[#101214] px-3 py-2.5 text-xs text-[#e3e7df] outline-none focus:border-[#d7fb58]" />
                  </label>
                  <label className="text-[11px] font-medium text-[#d3d8d2]">Release goal <span className="font-normal text-[#87908a]">optional</span>
                    <input maxLength={2000} value={releaseGoalDraft} onChange={(event) => setReleaseGoalDraft(event.target.value)} placeholder="e.g. share the single with existing listeners" className="mt-2 w-full rounded-lg border border-[#454c4e] bg-[#101214] px-3 py-2.5 text-xs text-[#e3e7df] outline-none focus:border-[#d7fb58]" />
                  </label>
                  <button type="submit" disabled={busy || !song || !intelligence} className="rounded-xl bg-[#d7fb58] px-4 py-3 text-xs font-semibold text-[#151813] disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Saving…" : "Create draft plan"}</button>
                </form>
                {releasePlans.length > 0 && (
                  <div className="mt-5 space-y-4">
                    {releasePlans.map((plan) => (
                      <article key={plan.plan_id} className="rounded-2xl border border-[#343a3d] bg-[#141719] p-5">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <h3 className="text-sm font-semibold text-[#e3e7df]">{plan.goal || "Release plan"}{plan.release_date ? ` · ${new Date(`${plan.release_date}T00:00:00`).toLocaleDateString()}` : ""}</h3>
                            <p className="mt-1 text-[10px] uppercase tracking-wider text-[#929a94]">{plan.status === "draft" ? "Draft for review" : "Approved plan · actions remain manual"}</p>
                          </div>
                          {plan.status === "draft" && <button type="button" disabled={busy} onClick={() => void approveReleasePlan(plan.plan_id)} className="rounded-lg border border-[#536044] px-3 py-2 text-[11px] font-medium text-[#d7fb58] disabled:opacity-50">Approve draft</button>}
                        </div>
                        <ol className="mt-4 divide-y divide-[#303638]">
                          {plan.tasks.map((task) => (
                            <li key={task.task_id} className="grid gap-1 py-3 md:grid-cols-[150px_1fr]">
                              <span className="text-[10px] uppercase tracking-wider text-[#aeb6aa]">{task.planned_date ? new Date(`${task.planned_date}T00:00:00`).toLocaleDateString() : `${task.day_offset > 0 ? "+" : ""}${task.day_offset} days`}</span>
                              <span><strong className="text-xs font-medium text-[#e3e7df]">{task.title}</strong><span className="mt-1 block text-[11px] leading-5 text-[#929a94]">{task.action}</span></span>
                            </li>
                          ))}
                        </ol>
                        <ul className="mt-3 space-y-1 border-t border-[#343a3d] pt-3 text-[10px] leading-5 text-[#87908a]">{plan.limitations.map((item) => <li key={item}>— {item}</li>)}</ul>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div className="flex items-start gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[#252b23] text-[#d7fb58]"><Video size={17} /></span>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Content / video</p>
                    <h2 className="mt-2 text-xl font-semibold">Render a private MP4.</h2>
                    <p className="mt-2 max-w-3xl text-xs leading-5 text-[#929a94]">Local FFmpeg creates deterministic waveform or spectrum motion graphics, title cards, and synchronized audio. No artwork upload, AI footage, or publishing is included. The full music video uses an opening title, reactive visual sequence, and closing card; it is not cinematic footage.</p>
                  </div>
                </div>
                {errorText && <p role="alert" className="mt-4 text-xs text-[#ff9a7d]">{errorText}</p>}
                <div className="mt-5 rounded-2xl border border-[#343a3d] bg-[#141719] p-4">
                  {promotionalConsentActive ? (
                    <p className="text-xs text-[#d7fb58]">Promotional-media consent is active for this song or workspace.</p>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <p className="max-w-2xl text-xs leading-5 text-[#b6beb6]">Rendering requires a separate opt-in for local promotional media generation, in addition to your rights declaration and audio-processing consent.</p>
                      <button type="button" disabled={busy || !song} onClick={() => void grantPromotionalConsent()} className="rounded-lg border border-[#536044] px-3 py-2 text-[11px] font-medium text-[#d7fb58] disabled:opacity-50">Grant video-generation consent</button>
                    </div>
                  )}
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button type="button" disabled={busy || !sourceAssetId || !promotionalConsentActive || !capabilities?.music_visualizer_render} onClick={() => void createVideoRender("music_visualizer")} className="flex items-center gap-2 rounded-xl bg-[#d7fb58] px-4 py-3 text-xs font-semibold text-[#151813] disabled:cursor-not-allowed disabled:opacity-45"><Video size={15} /> Render music visualizer</button>
                  <button type="button" disabled={busy || !sourceAssetId || !promotionalConsentActive || !capabilities?.full_music_video_render} onClick={() => void createVideoRender("full_music_video")} className="flex items-center gap-2 rounded-xl border border-[#454c4e] px-4 py-3 text-xs font-semibold text-[#e3e7df] hover:border-[#d7fb58] disabled:cursor-not-allowed disabled:opacity-45"><WandSparkles size={15} /> Render full music video</button>
                </div>
                {(!capabilities?.music_visualizer_render || !capabilities?.full_music_video_render) && <p className="mt-3 text-[11px] leading-5 text-[#ffb19b]">One or more video formats are unavailable. Install FFmpeg and FFprobe with drawtext, showwaves, showspectrum, libx264, AAC, and a system font, then restart the API.</p>}
                {videoRenders.length > 0 && (
                  <div className="mt-5 space-y-3">
                    {videoRenders.map((render) => (
                      <article key={render.render_id} className="rounded-2xl border border-[#343a3d] bg-[#141719] p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <h3 className="text-sm font-medium text-[#e3e7df]">{render.render_format === "music_visualizer" ? "Music visualizer" : "Full music video"}</h3>
                            <p className="mt-1 text-[10px] uppercase tracking-wider text-[#929a94]">{render.status === "failed" ? "Failed" : render.status === "succeeded" ? "MP4 ready · private" : `${render.status} · ${render.stage.replaceAll("_", " ")}`}</p>
                          </div>
                          {render.status === "succeeded" && (
                            <div className="flex items-center gap-2">
                              <button type="button" disabled={busy} onClick={() => void downloadVideoRender(render)} className="flex items-center gap-2 rounded-lg border border-[#536044] px-3 py-2 text-[11px] font-medium text-[#d7fb58] disabled:opacity-50"><ArrowDownToLine size={13} /> Download MP4</button>
                              {platformConnections.some((c) => c.provider === "youtube" && c.connected) && (
                                <button type="button" disabled={busy} onClick={() => void publishYouTube(render)} className="flex items-center gap-2 rounded-lg bg-[#d7fb58] px-3 py-2 text-[11px] font-medium text-[#151813] disabled:opacity-50"><Upload size={13} /> Publish to YouTube</button>
                              )}
                            </div>
                          )}
                        </div>
                        {(render.status === "queued" || render.status === "running") && (
                          <div className="mt-3">
                            <div role="progressbar" aria-label="Video render progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={render.progress_percent} className="h-1.5 overflow-hidden rounded-full bg-[#343a3d]">
                              <div className="h-full rounded-full bg-[#d7fb58] transition-all" style={{ width: `${render.progress_percent}%` }} />
                            </div>
                            <p className="mt-2 text-[10px] text-[#929a94]">{render.progress_percent}% · {render.stage.replaceAll("_", " ")}</p>
                          </div>
                        )}
                        {render.status === "failed" && <p role="alert" className="mt-3 text-xs text-[#ff9a7d]">{render.error?.message || "The local renderer could not complete this job."}</p>}
                        {render.status === "succeeded" && render.output_metadata && (
                          <p className="mt-2 text-[10px] text-[#929a94]">1280 × 720 MP4 · {typeof render.output_metadata.duration_seconds === "number" ? `${render.output_metadata.duration_seconds.toFixed(1)} seconds` : "duration validated"} · {render.output_size_bytes ? `${(render.output_size_bytes / 1024 / 1024).toFixed(1)} MB` : "size recorded"}</p>
                        )}
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#343a3d] bg-[#181b1e] px-6 py-4">
                <div className="flex items-center gap-3"><span className="grid h-8 w-8 place-items-center rounded-full bg-[#242a25] text-[#d7fb58]"><Check size={16} /></span><div><p className="text-xs font-medium">Private analysis complete</p><p className="mt-1 text-[10px] text-[#858d87]">Schema {intelligence.schema_version} · Analysis {intelligence.analysis_version} · Report {report.prompt_version}</p></div></div>
                <button type="button" onClick={downloadReport} className="flex items-center gap-2 text-xs text-[#bbc2bb] hover:text-[#d7fb58]">Download report JSON <ArrowDownToLine size={14} /></button>
              </div>
            </section>
          ) : phase === "onboarding" ? (
            <section className="mx-auto max-w-3xl">
              <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[.18em] text-[#d7fb58]"><CircleUserRound size={16} /> Artist workspace setup</div>
              <h1 className="mt-4 text-4xl font-semibold tracking-[-.05em]">{profile ? "Your artist profile" : "First, tell us about your project."}</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#a1a9a5]">This private context helps organize your workspace. It does not create an external artist account or connect any services.</p>
              {errorText && <p role="alert" className="mt-5 text-sm text-[#ff9a7d]">{errorText}</p>}
              <form onSubmit={saveArtistProfile} className="mt-8 grid gap-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:grid-cols-2 lg:p-8">
                <label className="text-xs font-medium text-[#d3d8d2]">Artist or project name <span className="text-[#ff9a7d]">*</span>
                  <input required maxLength={120} value={profileDraft.display_name} onChange={(event) => setProfileDraft((value) => ({ ...value, display_name: event.target.value }))} className="mt-2 w-full rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2]">Primary genre
                  <input maxLength={80} value={profileDraft.primary_genre ?? ""} onChange={(event) => setProfileDraft((value) => ({ ...value, primary_genre: event.target.value || null }))} className="mt-2 w-full rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="e.g. indie pop" />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2]">Preferred language
                  <input maxLength={32} value={profileDraft.language ?? ""} onChange={(event) => setProfileDraft((value) => ({ ...value, language: event.target.value || null }))} className="mt-2 w-full rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="e.g. English" />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2]">Target territories <span className="font-normal text-[#87908a]">(comma-separated)</span>
                  <input maxLength={1000} value={profileDraft.territories.join(", ")} onChange={(event) => setProfileDraft((value) => ({ ...value, territories: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} className="mt-2 w-full rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="e.g. United States, Canada" />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2] lg:col-span-2">Current goals <span className="font-normal text-[#87908a]">(comma-separated)</span>
                  <input maxLength={1000} value={profileDraft.goals.join(", ")} onChange={(event) => setProfileDraft((value) => ({ ...value, goals: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) }))} className="mt-2 w-full rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="e.g. finish an EP, build a live audience" />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2] lg:col-span-2">Short artist bio
                  <textarea maxLength={2000} rows={3} value={profileDraft.bio ?? ""} onChange={(event) => setProfileDraft((value) => ({ ...value, bio: event.target.value || null }))} className="mt-2 w-full resize-y rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="A short introduction, if you have one." />
                </label>
                <label className="text-xs font-medium text-[#d3d8d2] lg:col-span-2">Creative voice or preferences
                  <textarea maxLength={1000} rows={3} value={profileDraft.brand_voice ?? ""} onChange={(event) => setProfileDraft((value) => ({ ...value, brand_voice: event.target.value || null }))} className="mt-2 w-full resize-y rounded-xl border border-[#454c4e] bg-[#101214] px-4 py-3 text-sm text-[#f2f3eb] outline-none focus:border-[#d7fb58]" placeholder="Optional: describe the tone you want your artist communication to have." />
                </label>
                <div className="flex flex-wrap justify-between gap-3 border-t border-[#343a3d] pt-5 lg:col-span-2">
                  {profile ? <button type="button" onClick={() => setPhase("dashboard")} className="rounded-xl border border-[#454c4e] px-4 py-3 text-sm text-[#c4cbc4] hover:border-[#d7fb58]">Cancel</button> : <span className="self-center text-[11px] text-[#87908a]">You can update these details later.</span>}
                  <button disabled={busy} className="flex items-center gap-2 rounded-xl bg-[#d7fb58] px-5 py-3 text-sm font-semibold text-[#151813] hover:bg-[#e4ff86] disabled:opacity-60">{busy ? <LoaderCircle size={16} className="animate-spin" /> : null}{profile ? "Save profile" : "Save profile and continue"}<ArrowRight size={15} /></button>
                </div>
              </form>
            </section>
          ) : phase === "dashboard" ? (
            <section className="mx-auto max-w-6xl">
              <div className="flex flex-wrap items-end justify-between gap-5">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.18em] text-[#d7fb58]"><LayoutDashboard size={15} /> Artist workspace</div>
                  <h1 className="mt-4 text-4xl font-semibold tracking-[-.05em]">Welcome, {profile?.display_name}.</h1>
                  <p className="mt-3 text-sm text-[#a1a9a5]">Your private workbench for songs and release decisions.</p>
                </div>
                <div className="flex gap-3">
                  <button onClick={() => setPhase("onboarding")} className="flex items-center gap-2 rounded-xl border border-[#454c4e] px-4 py-3 text-sm text-[#d3d8d2] hover:border-[#d7fb58]"><CircleUserRound size={15} /> Edit profile</button>
                  <button onClick={() => { setErrorText(""); setPhase("studio"); }} className="flex items-center gap-2 rounded-xl bg-[#d7fb58] px-4 py-3 text-sm font-semibold text-[#151813] hover:bg-[#e4ff86]"><Plus size={16} /> Analyze a track</button>
                </div>
              </div>
              {errorText && <p role="alert" className="mt-5 text-sm text-[#ff9a7d]">{errorText}</p>}
              <div className="mt-8 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-[#343a3d] bg-[#181b1e] p-5"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[#929a94]">Song records</p><p className="mt-3 text-3xl font-semibold">{songCount}</p><p className="mt-1 text-xs text-[#87908a]">Saved in this private workspace</p></div>
                <div className="rounded-2xl border border-[#343a3d] bg-[#181b1e] p-5"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[#929a94]">Primary genre</p><p className="mt-3 text-xl font-semibold">{profile?.primary_genre || "Not set"}</p><p className="mt-1 text-xs text-[#87908a]">Artist context</p></div>
                <div className="rounded-2xl border border-[#343a3d] bg-[#181b1e] p-5"><p className="text-[10px] font-semibold uppercase tracking-[.15em] text-[#929a94]">Goals</p><p className="mt-3 truncate text-xl font-semibold">{profile?.goals[0] || "Add a goal"}</p><p className="mt-1 text-xs text-[#87908a]">{profile?.goals.length ? `${profile.goals.length} saved` : "Profile context"}</p></div>
              </div>
              <div className="mt-8 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div className="flex items-end justify-between gap-4">
                  <div><p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Your catalog</p><h2 className="mt-2 text-2xl font-semibold">Recent songs</h2></div>
                  <span className="text-xs text-[#929a94]">{songs.length} of {songCount} shown</span>
                </div>
                {songs.length ? (
                  <div className="mt-5 divide-y divide-[#303638]">
                    {songs.map((item) => (
                      <div key={item.song_id} className="flex items-center gap-4 py-4">
                        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#252b23] text-[#d7fb58]"><Music2 size={18} /></div>
                        <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-[#e5e9e2]">{item.title}</p><p className="mt-1 truncate text-xs text-[#929a94]">{item.artist_name || profile?.display_name} · {new Date(item.created_at).toLocaleDateString()}</p></div>
                        {item.genre_preferences[0] && <span className="hidden rounded-full border border-[#3b423c] px-3 py-1 text-[10px] text-[#aeb6aa] sm:inline-flex">{item.genre_preferences[0]}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-6 rounded-2xl border border-dashed border-[#454c4e] px-6 py-10 text-center">
                    <Music2 size={24} className="mx-auto text-[#89918b]" />
                    <p className="mt-3 text-sm font-medium">Your catalog starts with a song.</p>
                    <p className="mt-2 text-xs text-[#929a94]">Create a private song record and upload audio for analysis.</p>
                    <button onClick={() => setPhase("studio")} className="mt-5 text-xs font-semibold text-[#d7fb58] hover:text-[#e4ff86]">Open the listening room <ArrowRight size={13} className="ml-1 inline" /></button>
                  </div>
                )}
                {nextSongCursor && <button disabled={busy} onClick={() => void loadMoreSongs()} className="mt-5 rounded-lg border border-[#454c4e] px-4 py-2.5 text-xs text-[#d3d8d2] hover:border-[#d7fb58] disabled:opacity-50">{busy ? "Loading…" : "Load more songs"}</button>}
              </div>
              <div className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Read-only account links</p>
                  <h2 className="mt-2 text-2xl font-semibold">Social connections</h2>
                  <p className="mt-2 max-w-3xl text-xs leading-5 text-[#a1a9a5]">
                    Each provider requires its own approval. YouTube requests read-only channel access; Instagram is limited to professional accounts and basic profile access; Facebook links only the public profile. No Pages, posting, publishing, ads, or content changes are enabled.
                  </p>
                </div>
                {connectionMessage && <p role="status" className="mt-4 rounded-xl border border-[#45503c] bg-[#20251f] px-4 py-3 text-xs leading-5 text-[#d7fb58]">{connectionMessage}</p>}
                {errorText && <p role="alert" className="mt-4 text-xs text-[#ff9a7d]">{errorText}</p>}
                {!platformConnectionConsentActive ? (
                  <div className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#343a3d] bg-[#141719] p-4">
                    <p className="max-w-2xl text-xs leading-5 text-[#b6beb6]">Grant workspace consent before beginning a provider sign-in. You can withdraw it here at any time; withdrawal removes all locally stored provider tokens and cancels pending sign-ins.</p>
                    <button type="button" disabled={busy} onClick={() => void grantPlatformConnectionConsent()} className="rounded-lg border border-[#536044] px-3 py-2 text-[11px] font-medium text-[#d7fb58] disabled:opacity-50">Allow account connections</button>
                  </div>
                ) : (
                  <p className="mt-4 text-xs text-[#d7fb58]">Workspace platform-account connection consent is active. Provider authorization is still required separately.</p>
                )}
                <div className="mt-5 grid gap-3 lg:grid-cols-3">
                  {platformConnections.map((connection: PlatformConnection) => {
                    const label = connection.provider === "youtube" ? "YouTube" : connection.provider === "instagram" ? "Instagram" : "Facebook";
                    const statusLabel = connection.status === "connected" ? "Connected" :
                      connection.status === "expired" ? "Expired — reconnect" :
                        connection.status === "not_configured" ? "Needs app setup" : "Not connected";
                    return (
                      <div key={connection.provider} className="rounded-2xl border border-[#343a3d] bg-[#141719] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-[#e5e9e2]">{label}</p>
                            <p className="mt-1 truncate text-xs text-[#929a94]">{connection.account_name || statusLabel}</p>
                          </div>
                          <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[9px] uppercase tracking-wider ${connection.connected ? "border-[#45503c] text-[#d7fb58]" : "border-[#454c4e] text-[#929a94]"}`}>{statusLabel}</span>
                        </div>
                        {connection.expires_at && connection.connected && <p className="mt-2 text-[10px] text-[#929a94]">Token expires {new Date(connection.expires_at).toLocaleDateString()}.</p>}
                        <div className="mt-4 flex gap-2">
                          <button
                            type="button"
                            disabled={busy || !connection.configured || !platformConnectionConsentActive}
                            onClick={() => void startPlatformConnection(connection.provider)}
                            className="rounded-lg bg-[#d7fb58] px-3 py-2 text-[10px] font-semibold text-[#151813] disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            {connection.connected || connection.status === "expired" ? "Reconnect" : "Connect"}
                          </button>
                          {connection.account_id && <button type="button" disabled={busy} onClick={() => void disconnectPlatform(connection.provider)} className="rounded-lg border border-[#454c4e] px-3 py-2 text-[10px] text-[#d3d8d2] disabled:opacity-50">Remove local token</button>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="mt-5 rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                <div><p className="text-xs font-semibold uppercase tracking-[.16em] text-[#d7fb58]">Privacy controls</p><h2 className="mt-2 text-2xl font-semibold">Consent history</h2></div>
                {latestConsents.length ? (
                  <div className="mt-4 divide-y divide-[#303638]">
                    {latestConsents.map((consent) => (
                      <div key={consent.consent_id} className="flex flex-wrap items-center gap-3 py-4">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-[#e5e9e2]">{consent.consent_type.replaceAll("_", " ")}</p>
                          <p className="mt-1 text-xs text-[#929a94]">{consent.song_id ? `Song ${consent.song_id.slice(0, 8)}` : "Workspace-wide"} · {new Date(consent.created_at).toLocaleDateString()}</p>
                        </div>
                        <span className={`rounded-full border px-3 py-1 text-[10px] uppercase tracking-wider ${consent.granted ? "border-[#45503c] text-[#d7fb58]" : "border-[#454c4e] text-[#929a94]"}`}>{consent.granted ? "Active" : "Withdrawn"}</span>
                        {consent.granted && <button disabled={busy} onClick={() => void withdrawConsent(consent.consent_id)} className="text-xs text-[#ffad94] hover:text-[#ffc0ad] disabled:opacity-50">Withdraw</button>}
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-4 text-sm text-[#929a94]">No consent has been recorded for this workspace yet.</p>}
                <p className="mt-3 border-t border-[#343a3d] pt-4 text-[11px] leading-5 text-[#87908a]">Processing, third-party AI, promotional media, platform access, publishing, analytics, and model-training permissions are separate. Withdrawing platform-account consent immediately removes stored provider tokens and cancels pending sign-ins. Removing a local token does not revoke the app grant at the provider; use that provider&apos;s security settings for full revocation.</p>
              </div>
            </section>
          ) : (
            <section className="mx-auto max-w-5xl">
              <div className="flex flex-wrap items-end justify-between gap-5">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.19em] text-[#d7fb58]"><AudioLines size={15} /> The listening room</div>
                  <h1 className="mt-4 text-4xl font-semibold tracking-[-.05em] lg:text-5xl">Start with the sound.</h1>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-[#a1a9a5]">Add one unreleased track. We&apos;ll build a clear, versioned picture of what the audio actually tells us—without pretending to know what it doesn&apos;t.</p>
                </div>
                <span className="mb-1 flex items-center gap-2 rounded-full border border-[#343a3d] px-3 py-2 text-[10px] uppercase tracking-wider text-[#9ba39d]"><span className="h-1.5 w-1.5 rounded-full bg-[#d7fb58]" /> {capabilities?.openrouter_report ? "A&R provider ready" : "Offline report mode"}</span>
              </div>

              {errorText && <div role="alert" className="mt-6 flex items-start gap-3 rounded-xl border border-[#714438] bg-[#281c18] px-4 py-3 text-sm text-[#ffb19b]"><CircleAlert size={17} className="mt-0.5 shrink-0" /><span>{errorText}</span></div>}

              <form onSubmit={startAnalysis} className="mt-8 grid gap-5 lg:grid-cols-[.82fr_1.18fr]">
                <div className="rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#252b23] text-sm font-semibold text-[#d7fb58]">01</span>
                    <div><h2 className="text-sm font-semibold">Name the track</h2><p className="mt-1 text-[11px] text-[#87908a]">Start a private song record</p></div>
                  </div>
                  <label htmlFor="song-title" className="mb-2 mt-8 block text-xs font-medium text-[#d7dcd5]">Track title <span className="text-[#ff9a7d]">*</span></label>
                  <input id="song-title" value={songTitle} onChange={(event) => setSongTitle(event.target.value)} maxLength={255} required placeholder="e.g. The Long Way Home" className="w-full rounded-xl border border-[#3c4344] bg-[#101214] px-4 py-3.5 text-sm outline-none placeholder:text-[#8e9790] focus:border-[#d7fb58]" />
                  <label htmlFor="artist-name" className="mb-2 mt-5 block text-xs font-medium text-[#d7dcd5]">Artist name <span className="text-[#78817b]">optional</span></label>
                  <input id="artist-name" value={artistName} onChange={(event) => setArtistName(event.target.value)} maxLength={255} placeholder="How you want to be credited" className="w-full rounded-xl border border-[#3c4344] bg-[#101214] px-4 py-3.5 text-sm outline-none placeholder:text-[#8e9790] focus:border-[#d7fb58]" />
                  <label htmlFor="song-lyrics" className="mb-2 mt-5 block text-xs font-medium text-[#d7dcd5]">Lyrics <span className="text-[#78817b]">optional · artist-supplied</span></label>
                  <textarea id="song-lyrics" value={lyricsDraft} onChange={(event) => setLyricsDraft(event.target.value)} maxLength={30000} rows={5} placeholder="Paste lyrics you are authorized to provide. Analysis stays local." className="w-full resize-y rounded-xl border border-[#3c4344] bg-[#101214] px-4 py-3.5 text-sm leading-6 outline-none placeholder:text-[#8e9790] focus:border-[#d7fb58]" />
                  <p className="mt-2 text-[10px] leading-4 text-[#87908a]">The submitted text is analyzed locally and not retained. Only derived themes and repeated-line candidates are stored. They are not claims about listener response.</p>
                  <div className="mt-7 rounded-2xl border border-[#343a3d] bg-[#151719] p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-[#d8ded7]"><LockKeyhole size={14} className="text-[#d7fb58]" /> Kept in your local studio</div>
                    <p className="mt-2 pl-[22px] text-[11px] leading-5 text-[#87908a]">No third-party music upload, distribution, publishing, or ad spend. The default report runs offline.</p>
                  </div>
                  <div className="mt-5 grid gap-4 sm:grid-cols-2">
                    <label className="text-[11px] font-medium text-[#d3d8d2]">Sound recording rights
                      <select required value={recordingRightsBasis} onChange={(event) => setRecordingRightsBasis(event.target.value as RightsBasis)} className="mt-2 w-full rounded-lg border border-[#454c4e] bg-[#101214] px-3 py-3 text-xs text-[#e3e7df] outline-none focus:border-[#d7fb58]">
                        <option value="">Select your basis</option><option value="owned">I own or control it</option><option value="licensed">I have a license</option><option value="authorized">I am authorized to use it</option>
                      </select>
                    </label>
                    <label className="text-[11px] font-medium text-[#d3d8d2]">Composition rights
                      <select required value={compositionRightsBasis} onChange={(event) => setCompositionRightsBasis(event.target.value as RightsBasis)} className="mt-2 w-full rounded-lg border border-[#454c4e] bg-[#101214] px-3 py-3 text-xs text-[#e3e7df] outline-none focus:border-[#d7fb58]">
                        <option value="">Select your basis</option><option value="owned">I own or control it</option><option value="licensed">I have a license</option><option value="authorized">I am authorized to use it</option>
                      </select>
                    </label>
                  </div>
                  <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-[#343a3d] bg-[#151719] p-4 text-[11px] leading-5 text-[#b6beb6]">
                    <input required type="checkbox" checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} className="mt-1 accent-[#d7fb58]" />
                    <span>I confirm I own, control, or have authorization for both the sound recording and the underlying composition.</span>
                  </label>
                  <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-xl border border-[#343a3d] bg-[#151719] p-4 text-[11px] leading-5 text-[#b6beb6]">
                    <input required type="checkbox" checked={audioProcessingConsent} onChange={(event) => setAudioProcessingConsent(event.target.checked)} className="mt-1 accent-[#d7fb58]" />
                    <span>I separately consent to private processing of the audio file for the requested analysis. This does not authorize model training.</span>
                  </label>
                  <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-xl border border-[#343a3d] bg-[#151719] p-4 text-[11px] leading-5 text-[#b6beb6]">
                    <input required type="checkbox" checked={derivedAnalysisConsent} onChange={(event) => setDerivedAnalysisConsent(event.target.checked)} className="mt-1 accent-[#d7fb58]" />
                    <span>I separately consent to storing the derived Song Intelligence and A&amp;R report in my private workspace.</span>
                  </label>
                </div>

                <div className="rounded-3xl border border-[#343a3d] bg-[#181b1e] p-6 lg:p-8">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#252b23] text-sm font-semibold text-[#d7fb58]">02</span>
                    <div><h2 className="text-sm font-semibold">Bring the audio</h2><p className="mt-1 text-[11px] text-[#87908a]">A private, original file—not a public link</p></div>
                  </div>
                  <input ref={fileInput} type="file" accept="audio/*,.wav,.mp3,.flac,.ogg,.opus,.aac,.m4a" className="sr-only" aria-label="Choose an audio file" onChange={(event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0])} />
                  <div
                    onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
                    onDragOver={(event) => event.preventDefault()}
                    onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }}
                    onDrop={handleDrop}
                    className={`mt-8 grid min-h-[250px] place-items-center rounded-2xl border border-dashed px-6 py-8 text-center transition ${dragging ? "border-[#d7fb58] bg-[#d7fb58]/[.06]" : "border-[#454d4e] bg-[#141719] hover:border-[#798379]"}`}
                  >
                    {selectedFile ? (
                      <div>
                        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-[#273023] text-[#d7fb58]"><FileAudio2 size={23} /></div>
                        <p className="mt-4 max-w-xs truncate text-sm font-medium">{selectedFile.name}</p>
                        <p className="mt-1 text-xs text-[#8e9790]">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB · original kept private</p>
                        <button type="button" onClick={() => chooseFile(undefined)} className="mt-4 text-xs text-[#ff9a7d] hover:text-[#ffc0ad]">Remove file</button>
                      </div>
                    ) : (
                      <div>
                        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-[#242a25] text-[#d7fb58]"><Upload size={23} /></div>
                        <p className="mt-4 text-sm font-medium">Drop your audio into the room</p>
                        <p className="mt-2 text-xs text-[#89918b]">WAV, MP3, FLAC, OGG, M4A or AAC · up to 50 MB</p>
                        <button type="button" onClick={() => fileInput.current?.click()} className="mt-5 rounded-lg border border-[#4a5252] px-4 py-2.5 text-xs font-medium text-[#e2e6df] hover:border-[#d7fb58]">Browse files</button>
                      </div>
                    )}
                  </div>
                  <div className="mt-4 flex items-start gap-2 text-[11px] leading-5 text-[#929a94]"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-[#d7fb58]" /> The source file is validated by decoding. File extension and declared media type are not trusted.</div>
                  {capabilities?.openrouter_report && <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-[#343a3d] bg-[#151719] p-4 text-[11px] leading-5 text-[#b6beb6]">
                    <input type="checkbox" checked={thirdPartyAiConsent} onChange={(event) => setThirdPartyAiConsent(event.target.checked)} className="mt-1 accent-[#d7fb58]" />
                    <span><strong className="font-medium text-[#e1e6de]">Optional third-party AI report.</strong> I separately consent to sending the track title and structured audio measurements to the configured OpenRouter provider. The original audio is not sent. If unchecked, the app uses its offline report.</span>
                  </label>}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#343a3d] bg-[#181b1e] px-5 py-4 lg:col-span-2 lg:px-7">
                  <div className="flex items-center gap-2 text-xs text-[#a1a9a5]"><Check size={15} className="text-[#d7fb58]" /> First pass includes measurable audio facts and an evidence-limited A&R report.</div>
                  <button type="submit" disabled={busy || !selectedFile || !songTitle.trim() || !capabilities?.audio_analysis} className="flex items-center justify-center gap-2 rounded-xl bg-[#d7fb58] px-5 py-3.5 text-xs font-semibold text-[#151813] transition hover:bg-[#e4ff86] disabled:cursor-not-allowed disabled:opacity-45">
                    Analyze this track <ArrowRight size={15} />
                  </button>
                </div>
                {!capabilities?.audio_analysis && <p className="text-xs text-[#ffb19b] lg:col-span-2">Audio analysis is unavailable. Install FFmpeg and FFprobe, then restart the backend.</p>}
              </form>
            </section>
          )}
          <footer className="mt-16 flex flex-wrap items-center justify-between gap-3 border-t border-[#292e31] py-5 text-[10px] text-[#8e9790]">
            <span>AI MUSIC MARKETER <span className="mx-2 text-[#464e49]">/</span> PRIVATE FIRST</span>
            <span>Decision support only · No outcomes promised</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#d7fb58] text-[#151813]"><AudioLines size={21} strokeWidth={2.1} /></div>
      <div><div className="text-[13px] font-bold tracking-[.025em]">ROOM TONE</div><div className="mt-0.5 text-[9px] font-medium uppercase tracking-[.2em] text-[#858d87]">AI MUSIC MARKETER</div></div>
      {!compact && <span className="ml-1 rounded border border-[#343a3d] px-2 py-1 text-[9px] font-medium text-[#a0a8a1]">STUDIO</span>}
    </div>
  );
}

function ClaimList({ title, claims }: { title: string; claims: ARReport["recommendations"] }) {
  return (
    <div>
      <h3 className="text-[10px] font-semibold uppercase tracking-[.15em] text-[#9da69a]">{title}</h3>
      {claims.length ? (
        <ul className="mt-4 space-y-3">
          {claims.map((claim, index) => (
            <li key={`${claim.claim}-${index}`} className="flex gap-3 text-sm leading-6 text-[#d5d9d0]">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#d7fb58]" />
              <span>
                {claim.claim}
                <span className="ml-2 inline-flex rounded bg-[#292e28] px-1.5 py-0.5 align-middle text-[9px] uppercase tracking-wide text-[#aeb99c]">{claim.kind}</span>
                <span className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] leading-5 text-[#a1a9a5]" aria-label="Evidence references">
                  {claim.evidence_refs.length ? claim.evidence_refs.map((reference) => {
                    const featureKey = reference.startsWith("audio_features.")
                      ? reference.slice("audio_features.".length)
                      : null;
                    return featureKey ? (
                      <a
                        key={reference}
                        href={`#feature-${featureKey}`}
                        className="rounded border border-[#454c4e] px-1.5 hover:border-[#d7fb58] hover:text-[#d7fb58]"
                      >
                        Evidence: {featureLabel(featureKey)}
                      </a>
                    ) : (
                      <span key={reference} className="rounded border border-[#454c4e] px-1.5">
                        Evidence: {reference}
                      </span>
                    );
                  }) : <span>No direct audio evidence reference</span>}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="mt-4 text-xs leading-5 text-[#818a83]">The available evidence does not support a specific claim yet.</p>}
    </div>
  );
}

function featureLabel(key: string): string {
  const labels: Record<string, string> = {
    duration_seconds: "Duration",
    sample_rate: "Sample rate",
    channels: "Channels",
    tempo_bpm: "Tempo",
    rms_energy: "RMS energy",
    musical_key: "Musical key",
    essentia_tempo_bpm: "Essentia tempo",
  };
  return labels[key] ?? key.replaceAll("_", " ").replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function featureDisplay(key: string, feature: Intelligence["audio_features"][string]): string {
  const value = feature?.value;
  if (value === null || value === undefined || feature.status === "unavailable") return "Unavailable";
  if (key === "duration_seconds" && typeof value === "number") return formatDuration(value);
  if (key.endsWith("tempo_bpm") && typeof value === "number") return `${Math.round(value)} BPM`;
  if (key === "sample_rate" && typeof value === "number") return `${value.toLocaleString()} Hz`;
  if (key === "channels" && typeof value === "number") return `${value} ch`;
  if (key === "rms_energy" && typeof value === "number") return value.toFixed(4);
  if (typeof value === "string") return value;
  if (typeof value === "number") return `${value}${feature.unit ? ` ${feature.unit}` : ""}`;
  return JSON.stringify(value);
}

function FeatureTile({ id, label, feature, display }: { id: string; label: string; feature?: Intelligence["audio_features"][string]; display: string }) {
  return (
    <div id={id} className="scroll-mt-24 rounded-xl border border-[#343a3d] bg-[#141719] px-4 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-[#a0a8a1]">{label}</span>
        <span className="text-sm font-semibold tabular-nums text-[#f0f2e9]">{display}</span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[9px] uppercase tracking-wider text-[#8e9790]">
        <span>{feature?.status || "unavailable"}</span><span>Source: {feature?.source || "not configured"}</span>
      </div>
    </div>
  );
}
