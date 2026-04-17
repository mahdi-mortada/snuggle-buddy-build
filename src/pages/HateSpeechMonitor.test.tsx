import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

import HateSpeechMonitor from '@/pages/HateSpeechMonitor';

const mockFetchHateSpeechStats = vi.fn();
const mockFetchHateSpeechAllPosts = vi.fn();
const mockTriggerHateSpeechScan = vi.fn();
const mockReviewHateSpeechPost = vi.fn();
const mockFetchHateSpeechReplies = vi.fn();
const mockUseLiveData = vi.fn();

vi.mock('@/hooks/useLiveData', () => ({
  useLiveData: () => mockUseLiveData(),
}));

vi.mock('@/components/layout/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/services/backendApi', () => ({
  fetchHateSpeechStats: (...args: unknown[]) => mockFetchHateSpeechStats(...args),
  fetchHateSpeechAllPosts: (...args: unknown[]) => mockFetchHateSpeechAllPosts(...args),
  triggerHateSpeechScan: (...args: unknown[]) => mockTriggerHateSpeechScan(...args),
  reviewHateSpeechPost: (...args: unknown[]) => mockReviewHateSpeechPost(...args),
  fetchHateSpeechReplies: (...args: unknown[]) => mockFetchHateSpeechReplies(...args),
}));

describe('HateSpeechMonitor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    vi.spyOn(window, 'setInterval').mockImplementation((() => 1) as unknown as typeof window.setInterval);
    vi.spyOn(window, 'clearInterval').mockImplementation((() => undefined) as unknown as typeof window.clearInterval);

    mockUseLiveData.mockReturnValue({
      incidents: [],
      alerts: [],
      stats: {
        totalIncidents24h: 0,
        activeAlerts: 0,
        avgRiskScore: 0,
        riskTrend: 0,
        highestRiskRegion: 'Lebanon',
      },
      lastUpdated: new Date('2026-04-15T10:00:00Z').toISOString(),
      connectionStatus: 'connected',
    });

    mockFetchHateSpeechStats.mockResolvedValue({
      totalScraped: 2,
      totalFlagged: 1,
      flaggedLast24h: 1,
      flaggedLast1h: 1,
      byCategory: { sectarian: 1, clean: 1 },
      byCategoryLabels: { sectarian: 'Sectarian', clean: 'Clean' },
      byLanguage: { ar: 2 },
      topKeywords: [['keyword', 1]],
      lastScanAt: '2026-04-15T10:00:00Z',
      accountsFlagged: ['x_author'],
      trendingHashtags: ['LebanonNow'],
      topPostsByEngagement: [],
      hashtagTopPosts: { LebanonNow: ['x:111'] },
    });

    mockFetchHateSpeechAllPosts.mockResolvedValue([
      {
        id: 'x:111',
        platform: 'x',
        authorHandle: 'x_author',
        authorAgeDays: null,
        content: 'X post content',
        language: 'ar',
        hateScore: 72,
        category: 'sectarian',
        categoryLabel: 'Sectarian',
        isFlagged: true,
        keywordMatches: ['keyword'],
        modelConfidence: 0.9,
        likeCount: 10,
        retweetCount: 2,
        replyCount: 3,
        engagementTotal: 15,
        postedAt: '2026-04-15T09:00:00Z',
        scrapedAt: '2026-04-15T09:05:00Z',
        sourceUrl: 'https://x.com/x_author/status/111',
        hashtags: ['LebanonNow'],
        reviewed: false,
        reviewAction: '',
      },
      {
        id: 'tiktok:222',
        platform: 'tiktok',
        authorHandle: 'tt_author',
        authorAgeDays: null,
        content: 'TikTok post content',
        language: 'ar',
        hateScore: 48,
        category: 'clean',
        categoryLabel: 'Clean',
        isFlagged: false,
        keywordMatches: [],
        modelConfidence: 0.3,
        likeCount: 50,
        retweetCount: 4,
        replyCount: 6,
        engagementTotal: 60,
        postedAt: '2026-04-15T09:30:00Z',
        scrapedAt: '2026-04-15T09:35:00Z',
        sourceUrl: 'https://www.tiktok.com/@tt_author/video/222',
        hashtags: ['LebanonNow'],
        reviewed: false,
        reviewAction: '',
      },
    ]);

    mockFetchHateSpeechReplies.mockResolvedValue([]);
    mockTriggerHateSpeechScan.mockResolvedValue({ status: 'ok' });
    mockReviewHateSpeechPost.mockResolvedValue({ postId: 'x:111', action: 'confirmed' });
  });

  it('renders mixed-source posts including TikTok in the same feed', async () => {
    render(<HateSpeechMonitor />);

    await waitFor(() => {
      expect(screen.getAllByText('@x_author').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('@tt_author').length).toBeGreaterThan(0);
    expect(screen.getByText('TikTok')).toBeInTheDocument();
    expect(screen.getByText('X')).toBeInTheDocument();
  });

  it('keeps replies interaction for X posts only', async () => {
    render(<HateSpeechMonitor />);

    const replyTriggers = await screen.findAllByTitle('انقر لعرض التعليقات');
    expect(replyTriggers).toHaveLength(1);

    fireEvent.click(replyTriggers[0]);
    await waitFor(() => {
      expect(mockFetchHateSpeechReplies).toHaveBeenCalledWith('x:111', 10);
    });
    expect(mockFetchHateSpeechReplies).toHaveBeenCalledTimes(1);
  });
});
