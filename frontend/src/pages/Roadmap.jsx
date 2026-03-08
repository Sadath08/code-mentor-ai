import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
    Box, Typography, Card, CardContent, LinearProgress, Chip,
    Skeleton, Alert, Button, Grid, Divider, Collapse, IconButton,
    Tooltip,
} from '@mui/material';
import {
    Refresh, CheckCircle, RadioButtonUnchecked, Lock,
    ExpandMore, ExpandLess, ArrowForward, PlayCircleOutline,
    AccessTime, TrendingUp, EmojiEvents, Bolt,
} from '@mui/icons-material';
import PageContainer from '../components/layout/PageContainer';
import { useAuth } from '../context/AuthContext';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const GRAD = 'linear-gradient(135deg,#10b981,#3b82f6)';
const GRAD2 = 'linear-gradient(135deg,#6366f1,#8b5cf6)';
const HEAD = '#0f172a';
const BODY = '#475569';
const BORDER = '#e2e8f0';

// ── Company logos (text-based for robustness) ──────────────────
const COMPANIES = [
    { name: 'TCS', color: '#e74c3c', bg: '#fdf2f2' },
    { name: 'Infosys', color: '#1a6c37', bg: '#f0fff4' },
    { name: 'Amazon', color: '#ff9900', bg: '#fff8e6' },
    { name: 'Google', color: '#4285F4', bg: '#eff6ff' },
];

// ── Animated circular ring (pure CSS) ─────────────────────────
function CircularRing({ value = 0, size = 140, color = '#10b981', label, sub }) {
    const [displayed, setDisplayed] = useState(0);
    const r = (size / 2) - 14;
    const circ = 2 * Math.PI * r;
    const dash = (displayed / 100) * circ;

    useEffect(() => {
        let frame;
        let cur = 0;
        const step = () => {
            cur = Math.min(cur + 1.5, value);
            setDisplayed(Math.round(cur));
            if (cur < value) frame = requestAnimationFrame(step);
        };
        const t = setTimeout(() => { frame = requestAnimationFrame(step); }, 200);
        return () => { clearTimeout(t); cancelAnimationFrame(frame); };
    }, [value]);

    return (
        <Box sx={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
            <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
                <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={10} />
                <circle
                    cx={size / 2} cy={size / 2} r={r}
                    fill="none" stroke={color} strokeWidth={10}
                    strokeDasharray={`${dash} ${circ}`}
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dasharray 0.05s linear' }}
                />
            </svg>
            <Box sx={{
                position: 'absolute', inset: 0, display: 'flex',
                flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
                <Typography sx={{ fontWeight: 900, fontSize: size * 0.19, color: HEAD, lineHeight: 1 }}>
                    {displayed}<span style={{ fontSize: size * 0.11, color }}>%</span>
                </Typography>
                {label && <Typography sx={{ fontSize: 10, color: BODY, fontWeight: 700, textTransform: 'uppercase', mt: 0.3 }}>{label}</Typography>}
                {sub && <Typography sx={{ fontSize: 9, color: '#94a3b8', mt: 0.2 }}>{sub}</Typography>}
            </Box>
        </Box>
    );
}

// ── Placement hero banner ──────────────────────────────────────
function HeroBanner({ placementScore, currentWeek, totalWeeks, streak, completionPct }) {
    return (
        <Card sx={{
            borderRadius: 4, mb: 4, overflow: 'hidden', position: 'relative',
            background: 'linear-gradient(135deg,#0f172a 60%,#1e3a5f)',
            boxShadow: '0 20px 60px rgba(15,23,42,0.3)',
        }}>
            {/* Decorative blobs */}
            <Box sx={{ position: 'absolute', top: -40, right: -40, width: 200, height: 200, borderRadius: '50%', bgcolor: 'rgba(16,185,129,0.07)' }} />
            <Box sx={{ position: 'absolute', bottom: -30, left: '40%', width: 160, height: 160, borderRadius: '50%', bgcolor: 'rgba(59,130,246,0.07)' }} />

            <CardContent sx={{ p: { xs: 3, md: 4 }, position: 'relative', zIndex: 1 }}>
                <Grid container alignItems="center" spacing={3}>

                    {/* Left: text info */}
                    <Grid item xs={12} md={7}>
                        <Chip
                            label="🎯  Placement Readiness"
                            size="small"
                            sx={{ bgcolor: 'rgba(16,185,129,0.15)', color: '#34d399', fontWeight: 700, mb: 1.5, border: '1px solid rgba(52,211,153,0.3)' }}
                        />
                        <Typography sx={{ fontWeight: 900, fontSize: { xs: '1.6rem', md: '2rem' }, color: '#fff', lineHeight: 1.1, mb: 0.5 }}>
                            {placementScore >= 70 ? '🏆 Almost There!' : placementScore >= 40 ? '💪 Good Progress' : '🌱 Just Starting'}
                        </Typography>
                        <Typography sx={{ color: '#94a3b8', fontSize: 14, mb: 2.5 }}>
                            AI-generated roadmap · targets your Error DNA weaknesses
                        </Typography>

                        {/* Stats row */}
                        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                            {[
                                { label: 'Current Week', value: `Week ${currentWeek + 1} of ${totalWeeks}`, icon: '📅' },
                                { label: 'Streak', value: `🔥 ${streak} days`, icon: null },
                                { label: 'Progress', value: `${completionPct}% complete`, icon: null },
                            ].map(stat => (
                                <Box key={stat.label}>
                                    <Typography sx={{ color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, fontWeight: 600 }}>{stat.label}</Typography>
                                    <Typography sx={{ color: '#e2e8f0', fontWeight: 800, fontSize: 15 }}>{stat.value}</Typography>
                                </Box>
                            ))}
                        </Box>

                        {/* Company logos */}
                        <Box sx={{ mt: 2.5 }}>
                            <Typography sx={{ color: '#64748b', fontSize: 11, mb: 1, textTransform: 'uppercase', letterSpacing: 0.8 }}>Target companies</Typography>
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {COMPANIES.map(co => (
                                    <Box key={co.name} sx={{
                                        px: 1.5, py: 0.5, borderRadius: 2,
                                        bgcolor: 'rgba(255,255,255,0.07)',
                                        border: '1px solid rgba(255,255,255,0.12)',
                                        color: '#e2e8f0', fontWeight: 800, fontSize: 12,
                                        letterSpacing: 0.5,
                                    }}>
                                        {co.name}
                                    </Box>
                                ))}
                            </Box>
                        </Box>
                    </Grid>

                    {/* Right: rings */}
                    <Grid item xs={12} md={5}>
                        <Box sx={{ display: 'flex', gap: 2.5, justifyContent: { xs: 'flex-start', md: 'flex-end' }, flexWrap: 'wrap' }}>
                            <Box sx={{ textAlign: 'center' }}>
                                <CircularRing value={placementScore} size={130} color="#10b981" label="Readiness" />
                                <Typography sx={{ color: '#94a3b8', fontSize: 11, mt: 0.5, fontWeight: 600 }}>Placement Score</Typography>
                            </Box>
                            <Box sx={{ textAlign: 'center' }}>
                                <CircularRing value={completionPct} size={100} color="#6366f1" label="Done" />
                                <Typography sx={{ color: '#94a3b8', fontSize: 11, mt: 0.5, fontWeight: 600 }}>Roadmap Progress</Typography>
                            </Box>
                        </Box>
                    </Grid>
                </Grid>
            </CardContent>
        </Card>
    );
}

// ── Placement timeline ─────────────────────────────────────────
function PlacementTimeline({ currentWeek, totalWeeks, weeks }) {
    const milestones = [
        { label: 'Today', icon: '📍', week: 0, focus: weeks[0]?.focus || 'Getting started' },
        { label: 'Halfway', icon: '⚡', week: Math.floor(totalWeeks / 2), focus: weeks[Math.floor(totalWeeks / 2)]?.focus || 'Core concepts' },
        { label: 'Placement Ready', icon: '🏆', week: totalWeeks - 1, focus: weeks[totalWeeks - 1]?.focus || 'Mock interviews' },
    ];

    return (
        <Card sx={{ borderRadius: 3, mb: 4, border: `1px solid ${BORDER}`, overflow: 'hidden' }}>
            <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
                <Typography sx={{ fontWeight: 800, color: HEAD, fontSize: '1rem', mb: 2.5, display: 'flex', alignItems: 'center', gap: 1 }}>
                    🗺️ Your Placement Journey
                </Typography>

                {/* Timeline track */}
                <Box sx={{ position: 'relative', pt: 1 }}>
                    {/* Line */}
                    <Box sx={{ position: 'absolute', top: 22, left: '8%', right: '8%', height: 3, bgcolor: '#e2e8f0', borderRadius: 4 }} />
                    {/* Progress fill */}
                    <Box sx={{
                        position: 'absolute', top: 22, left: '8%',
                        width: `${Math.min((currentWeek / Math.max(totalWeeks - 1, 1)) * 84, 84)}%`,
                        height: 3, background: GRAD, borderRadius: 4,
                        transition: 'width 1.2s ease',
                    }} />

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}>
                        {milestones.map((m, i) => {
                            const done = currentWeek >= m.week;
                            return (
                                <Box key={i} sx={{ textAlign: 'center', flex: 1 }}>
                                    <Box sx={{
                                        width: 44, height: 44, borderRadius: '50%',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        mx: 'auto', mb: 1,
                                        bgcolor: done ? '#10b981' : '#f8fafc',
                                        border: `3px solid ${done ? '#10b981' : BORDER}`,
                                        fontSize: 20,
                                        boxShadow: done ? '0 4px 12px rgba(16,185,129,0.35)' : 'none',
                                        transition: 'all 0.6s ease',
                                    }}>
                                        {m.icon}
                                    </Box>
                                    <Typography sx={{ fontWeight: 800, fontSize: 13, color: done ? '#065f46' : HEAD }}>{m.label}</Typography>
                                    <Typography sx={{ fontSize: 11.5, color: BODY, mt: 0.3, maxWidth: 90, mx: 'auto', lineHeight: 1.4 }}>{m.focus}</Typography>
                                </Box>
                            );
                        })}
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
}

// ── Error DNA panel ────────────────────────────────────────────
function ErrorDNAPanel({ patterns, currentWeek }) {
    const [visible, setVisible] = useState(false);
    useEffect(() => { const t = setTimeout(() => setVisible(true), 600); return () => clearTimeout(t); }, []);

    if (!patterns?.length) return null;
    const top5 = patterns.slice(0, 5);
    const maxFreq = Math.max(...top5.map(p => p.frequency || p.count || 1));

    // Map concept → week (rough mapping: first concept → week 1, etc.)
    const conceptWeekMap = {};
    top5.forEach((p, i) => { conceptWeekMap[p.concept] = Math.min(i + 1, currentWeek + 2); });

    return (
        <Card sx={{ borderRadius: 3, mb: 4, border: '1px solid #fde68a', bgcolor: '#fffbeb', overflow: 'hidden' }}>
            <CardContent sx={{ p: { xs: 2.5, md: 3 } }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                    <Typography fontSize={22}>🧬</Typography>
                    <Box>
                        <Typography sx={{ fontWeight: 800, color: '#78350f', fontSize: '1rem' }}>Your Error DNA</Typography>
                        <Typography sx={{ fontSize: 12, color: '#92400e' }}>Concepts your roadmap is targeting based on submission patterns</Typography>
                    </Box>
                </Box>

                <Grid container spacing={2}>
                    {top5.map((p, i) => {
                        const freq = p.frequency || p.count || 1;
                        const pct = Math.round((freq / maxFreq) * 100);
                        const targetWeek = conceptWeekMap[p.concept];
                        const barColor = i === 0 ? '#e53935' : i === 1 ? '#fb8c00' : '#f9a825';

                        return (
                            <Grid item xs={12} key={i} sx={{
                                opacity: visible ? 1 : 0,
                                transform: visible ? 'translateX(0)' : 'translateX(-20px)',
                                transition: `all 0.5s ease ${i * 0.1}s`,
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                    <Box sx={{ minWidth: 130 }}>
                                        <Typography sx={{ fontWeight: 700, fontSize: 13, color: '#78350f', textTransform: 'capitalize' }}>
                                            {p.concept?.replace(/_/g, ' ')}
                                        </Typography>
                                    </Box>
                                    <Box sx={{ flex: 1 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box sx={{ flex: 1, height: 8, bgcolor: '#fde68a', borderRadius: 4, overflow: 'hidden' }}>
                                                <Box sx={{
                                                    height: '100%', borderRadius: 4,
                                                    bgcolor: barColor,
                                                    width: visible ? `${pct}%` : '0%',
                                                    transition: `width 0.7s ease ${0.3 + i * 0.1}s`,
                                                }} />
                                            </Box>
                                            <Typography sx={{ fontSize: 12, fontWeight: 700, color: barColor, minWidth: 32 }}>{pct}%</Typography>
                                        </Box>
                                    </Box>
                                    {/* Arrow + week mapping */}
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 70 }}>
                                        <Box sx={{
                                            width: visible ? 30 : 0, height: 2,
                                            bgcolor: '#f59e0b',
                                            transition: `width 0.6s ease ${0.4 + i * 0.12}s`,
                                            borderRadius: 1,
                                        }} />
                                        <Typography sx={{ fontSize: 11, color: '#92400e', fontWeight: 700, whiteSpace: 'nowrap' }}>
                                            → Wk {targetWeek}
                                        </Typography>
                                    </Box>
                                </Box>
                            </Grid>
                        );
                    })}
                </Grid>
            </CardContent>
        </Card>
    );
}

// ── Topic card ─────────────────────────────────────────────────
const TOPIC_STATUS = [
    { key: 'not_started', label: 'Not Started', color: '#94a3b8' },
    { key: 'in_progress', label: 'In Progress', color: '#f59e0b' },
    { key: 'completed', label: 'Done ✓', color: '#10b981' },
];

function TopicCard({ topic }) {
    const navigate = useNavigate();
    const [status, setStatus] = useState('not_started');
    const s = TOPIC_STATUS.find(x => x.key === status) || TOPIC_STATUS[0];

    return (
        <Card sx={{
            borderRadius: 2.5, border: `1px solid ${BORDER}`, mb: 1.5,
            transition: 'all .2s ease',
            '&:hover': { transform: 'translateY(-2px)', boxShadow: '0 6px 20px rgba(16,185,129,0.1)', borderColor: '#a7f3d0' },
        }}>
            <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'flex-start' }}>
                    <Box flex={1}>
                        <Typography sx={{ fontWeight: 700, color: HEAD, fontSize: '0.9rem', mb: 0.5 }}>
                            📌 {topic.name}
                        </Typography>
                        {topic.why && (
                            <Typography sx={{ color: BODY, fontSize: 12.5, lineHeight: 1.6, mb: 1 }}>{topic.why}</Typography>
                        )}
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            {topic.estimated_time && (
                                <Chip icon={<AccessTime sx={{ fontSize: '11px !important' }} />} label={topic.estimated_time}
                                    size="small" sx={{ bgcolor: '#f1f5f9', color: BODY, fontSize: 11, height: 22 }} />
                            )}
                            {(topic.resources || []).slice(0, 2).map(r => (
                                <Chip key={r} label={r} size="small" sx={{ bgcolor: '#eff6ff', color: '#1d4ed8', fontSize: 11, height: 22 }} />
                            ))}
                        </Box>
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1, minWidth: 90 }}>
                        <Box
                            onClick={() => {
                                const idx = TOPIC_STATUS.findIndex(x => x.key === status);
                                setStatus(TOPIC_STATUS[(idx + 1) % TOPIC_STATUS.length].key);
                            }}
                            sx={{
                                cursor: 'pointer', px: 1.2, py: 0.4, borderRadius: 1.5,
                                border: `1px solid ${BORDER}`, fontSize: 11, fontWeight: 700,
                                color: s.color, bgcolor: '#f8fafc', transition: 'all .15s',
                                '&:hover': { borderColor: '#10b981' },
                            }}
                        >
                            {s.label}
                        </Box>
                        <Button size="small"
                            onClick={() => navigate('/submit', { state: { topicName: topic.name, hint: topic.why || '' } })}
                            endIcon={<ArrowForward sx={{ fontSize: '13px !important' }} />}
                            sx={{ background: GRAD, color: '#fff', fontWeight: 700, textTransform: 'none', borderRadius: 1.5, fontSize: 11, px: 1.5, py: 0.5, minWidth: 70 }}
                        >
                            Practice
                        </Button>
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
}

// ── Week card (3 states) ────────────────────────────────────────
function WeekCard({ week, index, active, completed, locked, patterns, animDelay = 0 }) {
    const [open, setOpen] = useState(active);
    const [mounted, setMounted] = useState(false);
    useEffect(() => { const t = setTimeout(() => setMounted(true), animDelay); return () => clearTimeout(t); }, [animDelay]);

    const weekNum = index + 1;
    const topics = week.topics || [];
    const donePct = topics.filter(t => t.status === 'completed').length / Math.max(topics.length, 1) * 100;

    let borderColor = BORDER, bgColor = '#fff', leftColor = 'transparent', shadow = '0 1px 6px rgba(0,0,0,0.04)';
    if (active) { borderColor = '#a7f3d0'; bgColor = '#f0fdf4'; leftColor = '#10b981'; shadow = '0 6px 24px rgba(16,185,129,0.12)'; }
    if (completed) { borderColor = '#bbf7d0'; bgColor = '#f9fffe'; leftColor = '#34d399'; }
    if (locked) { bgColor = '#fdfdfd'; }

    return (
        <Card sx={{
            borderRadius: '16px', border: `1px solid ${borderColor}`,
            borderLeft: `4px solid ${leftColor}`, bgcolor: bgColor, mb: 2.5,
            opacity: locked ? 0.45 : mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(12px)',
            transition: `opacity 0.4s ease ${animDelay}ms, transform 0.4s ease ${animDelay}ms, box-shadow .2s`,
            pointerEvents: locked ? 'none' : 'auto',
            boxShadow: active ? shadow : '0 1px 6px rgba(0,0,0,0.04)',
        }}>
            <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
                {/* Header */}
                <Box
                    onClick={() => !locked && setOpen(o => !o)}
                    sx={{
                        display: 'flex', alignItems: 'center', gap: 2,
                        px: 3, py: 2.5, cursor: locked ? 'default' : 'pointer',
                        borderRadius: '16px 16px 0 0',
                        '&:hover': locked ? {} : { bgcolor: 'rgba(0,0,0,0.01)' },
                    }}
                >
                    <Box sx={{ fontSize: 22, flexShrink: 0 }}>
                        {locked ? '🔒'
                            : completed ? <CheckCircle sx={{ color: '#10b981', fontSize: 24 }} />
                                : active ? <PlayCircleOutline sx={{ color: '#10b981', fontSize: 24 }} />
                                    : <RadioButtonUnchecked sx={{ color: '#94a3b8', fontSize: 24 }} />}
                    </Box>

                    <Box flex={1}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
                            <Typography sx={{ fontWeight: 700, color: locked ? '#94a3b8' : HEAD, fontSize: '1rem' }}>
                                Week {weekNum}: {week.focus}
                            </Typography>
                            {active && <Chip label="Active 🎯" size="small" sx={{ bgcolor: '#10b981', color: '#fff', fontWeight: 700, fontSize: 11 }} />}
                            {completed && <Chip label="Completed ✓" size="small" sx={{ bgcolor: '#d1fae5', color: '#065f46', fontWeight: 700, fontSize: 11 }} />}
                            {locked && <Chip label="Locked" size="small" icon={<Lock sx={{ fontSize: '11px !important' }} />} sx={{ bgcolor: '#f1f5f9', color: '#94a3b8', fontWeight: 600, fontSize: 11 }} />}
                        </Box>
                        {week.practice_goal && !locked && (
                            <Typography sx={{ fontSize: 12.5, color: BODY, mt: 0.3 }}>🎯 {week.practice_goal}</Typography>
                        )}
                        {locked && topics.slice(0, 3).length > 0 && (
                            <Typography sx={{ fontSize: 11.5, color: '#94a3b8', mt: 0.3 }}>
                                {topics.slice(0, 3).map(t => t.name).join(' · ')}{topics.length > 3 ? ' · …' : ''}
                            </Typography>
                        )}
                        {/* Active week progress bar */}
                        {active && topics.length > 0 && (
                            <Box sx={{ mt: 1 }}>
                                <LinearProgress variant="determinate" value={donePct}
                                    sx={{ height: 5, borderRadius: 3, bgcolor: '#d1fae5', '& .MuiLinearProgress-bar': { background: GRAD, borderRadius: 3 } }} />
                                <Typography sx={{ fontSize: 10, color: '#065f46', mt: 0.3, fontWeight: 600 }}>{Math.round(donePct)}% topics marked done</Typography>
                            </Box>
                        )}
                    </Box>

                    {!locked && (
                        <IconButton size="small" sx={{ color: '#94a3b8' }}>
                            {open ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                    )}
                </Box>

                {/* Expandable body */}
                <Collapse in={open && !locked}>
                    <Divider sx={{ borderColor }} />
                    <Box sx={{ px: 3, py: 2.5 }}>
                        {active && patterns?.length > 0 && (
                            <Box sx={{ bgcolor: '#fffbeb', border: '1px solid #fde68a', borderRadius: 2, p: 1.5, mb: 2 }}>
                                <Typography sx={{ fontWeight: 700, color: '#92400e', fontSize: 12.5 }}>
                                    ⚠️ Targeting your top error: <b>{patterns[0]?.concept?.replace(/_/g, ' ')}</b> — this week fixes it.
                                </Typography>
                            </Box>
                        )}
                        {topics.length === 0
                            ? <Typography sx={{ color: BODY, fontSize: 14 }}>No topics listed.</Typography>
                            : topics.map((topic, ti) => <TopicCard key={ti} topic={topic} />)
                        }
                    </Box>
                </Collapse>
            </CardContent>
        </Card>
    );
}

// ── Main Page ──────────────────────────────────────────────────
export default function Roadmap() {
    const { user, token } = useAuth();
    const [data, setData] = useState(null);          // full API response
    const [patterns, setPatterns] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [activeStep, setActiveStep] = useState(0);

    const fetchAll = async (force = false) => {
        if (!user?.id) return;
        setLoading(true); setError('');
        try {
            const [rmRes, ptRes] = await Promise.allSettled([
                axios.get(`${API_BASE}/api/roadmap/${user.id}${force ? '?regenerate=true' : ''}`,
                    { headers: { Authorization: `Bearer ${token}` } }),
                axios.get(`${API_BASE}/api/analytics/error-patterns/${user.id}`,
                    { headers: { Authorization: `Bearer ${token}` } }),
            ]);
            if (rmRes.status === 'fulfilled') {
                setData(rmRes.value.data);
                setActiveStep(rmRes.value.data.current_week || 0);
            } else {
                setError('Could not load roadmap. Click Regenerate to create one.');
            }
            if (ptRes.status === 'fulfilled') setPatterns(ptRes.value.data.breakdown || []);
        } catch (err) {
            setError('Could not load roadmap. Is the backend running?');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchAll(); }, [user]);

    if (!user) return (
        <PageContainer maxWidth="md">
            {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} variant="rectangular" height={90} sx={{ borderRadius: 3, mb: 2 }} />
            ))}
        </PageContainer>
    );

    const roadmap = data?.roadmap || {};
    const weeks = roadmap.weeks || [];
    const totalWeeks = weeks.length;
    const currentWeek = activeStep;
    const placementScore = data?.placement_score ?? 0;
    const completionPct = data?.completion_pct ?? 0;
    const streak = data?.streak ?? 0;

    return (
        <PageContainer maxWidth="md">
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3, flexWrap: 'wrap', gap: 2 }}>
                <Box>
                    <Typography variant="h5" sx={{ fontWeight: 800, color: HEAD }}>🗺️ Your Learning Roadmap</Typography>
                    <Typography sx={{ color: BODY, fontSize: 14, mt: 0.3 }}>AI-generated · targets your Error DNA weaknesses</Typography>
                </Box>
                <Button variant="outlined" startIcon={<Refresh />} size="small"
                    onClick={() => fetchAll(true)} disabled={loading}
                    sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 700, borderColor: BORDER }}>
                    Regenerate
                </Button>
            </Box>

            {error && (
                <Alert severity="warning" sx={{ mb: 3, borderRadius: 2 }}
                    action={<Button size="small" color="inherit" onClick={() => fetchAll(true)}>Regenerate</Button>}>
                    {error}
                </Alert>
            )}

            {loading ? (
                <>
                    <Skeleton variant="rectangular" height={220} sx={{ borderRadius: 4, mb: 4 }} />
                    <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 3, mb: 3 }} />
                    {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} variant="rectangular" height={80} sx={{ borderRadius: 2, mb: 2 }} />)}
                </>
            ) : (
                <>
                    {/* Hero banner */}
                    <HeroBanner
                        placementScore={placementScore}
                        currentWeek={currentWeek}
                        totalWeeks={totalWeeks || 6}
                        streak={streak}
                        completionPct={completionPct}
                    />

                    {/* Placement timeline */}
                    {totalWeeks > 0 && (
                        <PlacementTimeline
                            currentWeek={currentWeek}
                            totalWeeks={totalWeeks}
                            weeks={weeks}
                        />
                    )}

                    {/* Error DNA panel */}
                    <ErrorDNAPanel patterns={patterns} currentWeek={currentWeek} />

                    {/* Summary chips */}
                    {totalWeeks > 0 && (
                        <Box sx={{ display: 'flex', gap: 1.5, mb: 3.5, flexWrap: 'wrap' }}>
                            <Chip label={`${totalWeeks} Weeks`} sx={{ bgcolor: '#dbeafe', color: '#1e40af', fontWeight: 700 }} />
                            <Chip
                                label={`${weeks.reduce((a, w) => a + (w.topics?.length || 0), 0)} Topics`}
                                sx={{ bgcolor: '#f0fdf4', color: '#065f46', fontWeight: 700 }}
                            />
                            {patterns[0] && (
                                <Chip
                                    icon={<TrendingUp sx={{ color: '#d97706 !important', fontSize: '16px !important' }} />}
                                    label={`Top issue: ${patterns[0].concept?.replace(/_/g, ' ')}`}
                                    sx={{ bgcolor: '#fffbeb', color: '#92400e', fontWeight: 600, border: '1px solid #fde68a' }}
                                />
                            )}
                        </Box>
                    )}

                    {/* Week cards */}
                    {totalWeeks === 0 ? (
                        <Card sx={{ borderRadius: 3, p: 4, textAlign: 'center', bgcolor: '#f0fdf4', border: '1px solid #bbf7d0' }}>
                            <Typography fontSize={40} mb={1}>🌱</Typography>
                            <Typography fontWeight={700} color={HEAD} mb={1}>No roadmap yet</Typography>
                            <Typography color={BODY} fontSize={14} mb={2}>
                                Submit some code first — the AI will generate a personalized roadmap based on your mistakes.
                            </Typography>
                            <Button onClick={() => fetchAll(true)}
                                sx={{ background: GRAD, color: '#fff', borderRadius: 2, textTransform: 'none', fontWeight: 700, px: 3 }}
                                startIcon={<Refresh />}>
                                Generate Now
                            </Button>
                        </Card>
                    ) : (
                        weeks.map((week, idx) => (
                            <WeekCard
                                key={idx}
                                week={week}
                                index={idx}
                                active={idx === currentWeek}
                                completed={idx < currentWeek}
                                locked={idx > currentWeek}
                                patterns={patterns}
                                animDelay={idx * 80}
                            />
                        ))
                    )}

                    {/* Week navigation */}
                    {totalWeeks > 1 && (
                        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mt: 3 }}>
                            <Button variant="outlined"
                                disabled={currentWeek === 0}
                                onClick={() => setActiveStep(s => Math.max(0, s - 1))}
                                sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 700, borderColor: BORDER }}>
                                ← Previous Week
                            </Button>
                            <Button
                                disabled={currentWeek >= totalWeeks - 1}
                                onClick={() => setActiveStep(s => Math.min(totalWeeks - 1, s + 1))}
                                sx={{
                                    background: GRAD, color: '#fff', borderRadius: 2, textTransform: 'none', fontWeight: 700,
                                    '&:hover': { opacity: 0.9 },
                                    '&.Mui-disabled': { background: BORDER, color: '#94a3b8' },
                                }}>
                                Complete &amp; Next Week →
                            </Button>
                        </Box>
                    )}
                </>
            )}
        </PageContainer>
    );
}
