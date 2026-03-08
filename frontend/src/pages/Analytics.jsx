import { useState, useEffect } from 'react';
import axios from 'axios';
import {
    Box, Typography, Grid, Card, CardContent,
    Tabs, Tab, Skeleton, Alert, Chip, LinearProgress,
} from '@mui/material';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    LineChart, Line, Cell,
} from 'recharts';
import { TrendingUp, EmojiEvents } from '@mui/icons-material';
import PageContainer from '../components/layout/PageContainer';
import { useAuth } from '../context/AuthContext';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const COLORS = ['#1976d2', '#ff9800', '#4caf50', '#e91e63', '#9c27b0', '#00bcd4'];

function TabPanel({ children, value, index }) {
    return value === index ? <Box sx={{ pt: 3 }}>{children}</Box> : null;
}

export default function Analytics() {
    console.log('Rendering Analytics page');
    const { user, token } = useAuth();
    const [tab, setTab] = useState(0);
    const [stats, setStats] = useState(null);
    const [patterns, setPatterns] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!user?.id) return;
        const fetchAll = async () => {
            setLoading(true);
            setError('');
            try {
                const res = await axios.get(`${API_BASE}/api/analytics/${user.id}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                setStats(res.data);
            } catch (err) {
                console.error('Analytics fetch error:', err);
                setError('Could not load analytics. Is the backend running?');
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, [user]);

    if (!user) {
        return (
            <PageContainer>
                <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 3 }} />
            </PageContainer>
        );
    }

    if (error) {
        return (
            <PageContainer>
                <Alert severity="error" sx={{ borderRadius: 2 }}>{error}</Alert>
            </PageContainer>
        );
    }

    const scoreData = stats?.score_trend || [];
    const conceptData = stats?.error_dna || [];

    // Sort concepts to find top pattern
    const sortedConcepts = [...conceptData].sort((a, b) => b.count - a.count);
    const topConcept = sortedConcepts.length > 0 ? sortedConcepts[0] : null;

    return (
        <PageContainer>
            <Typography variant="h5" fontWeight={800} gutterBottom>📊 Analytics</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Deep insights into your coding performance
            </Typography>

            {/* Summary Stat Row */}
            <Grid container spacing={2} sx={{ mb: 4 }}>
                {[
                    { label: 'Streak', value: stats?.streak, icon: '🔥', color: '#ff5722' },
                    { label: 'Submissions', value: stats?.submissions, icon: '💻', color: '#1976d2' },
                    { label: 'Improvement', value: `${stats?.improvement || 0}%`, icon: '📈', color: '#4caf50' },
                    { label: 'Placement Readiness', value: `${stats?.placement_readiness || 0}%`, icon: '🎯', color: '#9c27b0' },
                ].map(({ label, value, icon, color }) => (
                    <Grid item xs={6} md={3} key={label}>
                        <Card sx={{ borderRadius: 3 }}>
                            <CardContent sx={{ p: 2.5 }}>
                                {loading ? <Skeleton height={60} /> : (
                                    <>
                                        <Typography fontSize={28}>{icon}</Typography>
                                        <Typography variant="h5" fontWeight={800} color={color}>{value ?? '—'}</Typography>
                                        <Typography variant="body2" color="text.secondary">{label}</Typography>
                                    </>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {/* Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 1 }}>
                <Tabs value={tab} onChange={(_, v) => setTab(v)}>
                    <Tab label="Score Trend" />
                    <Tab label="Error DNA" />
                    <Tab label="Top Patterns" />
                </Tabs>
            </Box>

            {/* Score Trend */}
            <TabPanel value={tab} index={0}>
                {loading ? <Skeleton variant="rectangular" height={260} sx={{ borderRadius: 2 }} /> :
                    scoreData.length === 0 ? (
                        <Alert severity="info" sx={{ borderRadius: 2 }}>
                            No submission scores yet. Submit some code to see your progress chart! 🚀
                        </Alert>
                    ) : (
                        <Card sx={{ borderRadius: 3, p: 2 }}>
                            <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Confidence Score Over Submissions</Typography>
                            <ResponsiveContainer width="100%" height={240}>
                                <LineChart data={scoreData}>
                                    <XAxis dataKey="submission" tickFormatter={(v) => `#${v}`} />
                                    <YAxis domain={[0, 100]} />
                                    <Tooltip formatter={(v) => [`${v}%`, 'Confidence']} labelFormatter={(label) => `Submission #${label}`} />
                                    <Line type="monotone" dataKey="score" stroke="#1976d2" strokeWidth={2} dot={{ r: 4 }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </Card>
                    )}
            </TabPanel>

            {/* Error DNA Bar Chart */}
            <TabPanel value={tab} index={1}>
                {loading ? <Skeleton variant="rectangular" height={260} sx={{ borderRadius: 2 }} /> :
                    conceptData.length === 0 ? (
                        <Alert severity="info" sx={{ borderRadius: 2 }}>
                            No error patterns recorded yet. Submit code to start building your Error DNA! 🔬
                        </Alert>
                    ) : (
                        <Card sx={{ borderRadius: 3, p: 2 }}>
                            <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Error Frequency by Concept</Typography>
                            <ResponsiveContainer width="100%" height={260}>
                                <BarChart data={conceptData} layout="vertical" margin={{ left: 20 }}>
                                    <XAxis type="number" hide />
                                    <YAxis type="category" dataKey="concept" width={150} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => [`${v} errors`, 'Count']} />
                                    <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                                        {conceptData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </Card>
                    )}
            </TabPanel>

            {/* Top Patterns List */}
            <TabPanel value={tab} index={2}>
                {loading ? <Skeleton variant="rectangular" height={160} sx={{ borderRadius: 2 }} /> :
                    !topConcept ? (
                        <Alert severity="info" sx={{ borderRadius: 2 }}>No recurring patterns yet. Keep submitting! 💪</Alert>
                    ) : (
                        <Card sx={{ borderRadius: 3 }}>
                            <CardContent sx={{ p: 4, textAlign: 'center' }}>
                                <EmojiEvents sx={{ fontSize: 60, color: '#ff9800', mb: 2 }} />
                                <Typography variant="h5" fontWeight={800} gutterBottom>
                                    Highest Frequency Error
                                </Typography>
                                <Typography variant="h6" color="text.secondary" fontWeight={500} sx={{ mb: 3 }}>
                                    <Typography component="span" variant="h5" fontWeight={800} color="error.main">
                                        {topConcept.concept}
                                    </Typography>
                                    {' '}— {topConcept.count} errors
                                </Typography>
                                <Chip
                                    label="Recommended: Play Code Games based on this concept"
                                    color="primary"
                                    variant="outlined"
                                    sx={{ fontWeight: 600, px: 2, py: 2.5, fontSize: 15 }}
                                />
                            </CardContent>
                        </Card>
                    )}
            </TabPanel>
        </PageContainer>
    );
}
