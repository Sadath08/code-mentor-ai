import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
    Box, Typography, Grid, Card, CardContent, Chip, Button,
    Skeleton, Alert, LinearProgress, Divider, RadioGroup,
    FormControlLabel, Radio, CircularProgress,
} from '@mui/material';
import {
    SportsEsports, CheckCircle, Cancel, AutoAwesome, Lightbulb,
    AccessTime, CrisisAlert, LocalFireDepartment, EmojiEvents, Replay,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../components/layout/PageContainer';
import { useAuth } from '../context/AuthContext';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const GAME_CARDS = [
    { id: 'debug_the_bug', title: 'Debug the Bug', icon: '🐛', color: '#e53935', diff: 'Medium', time: '5 min', skill: 'Debugging logic errors' },
    { id: 'predict_output', title: 'Predict Output', icon: '🎯', color: '#1976d2', diff: 'Hard', time: '4 min', skill: 'Tracing execution flow' },
    { id: 'code_jumble', title: 'Code Jumble', icon: '🧩', color: '#7b1fa2', diff: 'Easy', time: '4 min', skill: 'Syntax & Structure' },
    { id: 'syntax_sprint', title: 'Syntax Sprint', icon: '⚡', color: '#f57c00', diff: 'Easy', time: '3 min', skill: 'Compile-time errors' },
    { id: 'trivia', title: 'Code Trivia', icon: '🎓', color: '#388e3c', diff: 'Easy', time: '3 min', skill: 'CS Theory' },
];

// ─── Session view states ────────────────────────────────────────────────────
const VIEW = { LOBBY: 'lobby', LOADING: 'loading', QUESTION: 'question', SCORE: 'score' };

export default function Games() {
    const { user, token } = useAuth();
    const navigate = useNavigate();

    // ── Persistent stats ──────────────────────────────────────────────────
    const [allTimeScore, setAllTimeScore] = useState(() => parseInt(localStorage.getItem('gameScore') || '0', 10));
    const [streak, setStreak] = useState(() => parseInt(localStorage.getItem('gameStreak') || '0', 10));
    const [lastPlayed, setLastPlayed] = useState(() => localStorage.getItem('gameLastPlayed') || '');

    // ── Current session state ─────────────────────────────────────────────
    const [view, setView] = useState(VIEW.LOBBY);
    const [gameType, setGameType] = useState('');
    const [session, setSession] = useState(null);     // full session object from backend
    const [questions, setQuestions] = useState([]);   // array of 5 questions
    const [current, setCurrent] = useState(0);        // current question index
    const [selected, setSelected] = useState('');
    const [answered, setAnswered] = useState(false);
    const [sessionAnswers, setSessionAnswers] = useState([]); // {q, selected, correct, points}
    const [sessionScore, setSessionScore] = useState(0);
    const [startTime, setStartTime] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        localStorage.setItem('gameScore', allTimeScore.toString());
        localStorage.setItem('gameStreak', streak.toString());
        localStorage.setItem('gameLastPlayed', lastPlayed);
    }, [allTimeScore, streak, lastPlayed]);

    if (!user) return <PageContainer><Skeleton variant="rectangular" height={400} sx={{ borderRadius: 3 }} /></PageContainer>;

    // ── Streak helper ─────────────────────────────────────────────────────
    const touchStreak = () => {
        const today = new Date().toDateString();
        if (lastPlayed !== today) {
            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            setStreak(s => lastPlayed === yesterday.toDateString() ? s + 1 : 1);
            setLastPlayed(today);
        }
    };

    // ── Start session ─────────────────────────────────────────────────────
    const startSession = async (type) => {
        setGameType(type);
        setView(VIEW.LOADING);
        setError('');
        setSessionAnswers([]);
        setSessionScore(0);
        setCurrent(0);
        setSelected('');
        setAnswered(false);

        try {
            const { data } = await axios.get(`${API_BASE}/api/game/questions`, {
                params: { user_id: user.id, game_type: type },
                headers: { Authorization: `Bearer ${token}` },
            });
            setSession(data);
            setQuestions(data.questions || []);
            setView(VIEW.QUESTION);
            setStartTime(Date.now());
        } catch (err) {
            console.error('Game session error:', err);
            setError('Could not load questions. Please try again.');
            setView(VIEW.LOBBY);
        }
    };

    // ── Submit answer ─────────────────────────────────────────────────────
    const handleSubmit = () => {
        if (!selected) return;
        const q = questions[current];
        const isCorrect = selected === q.correct_answer;
        const timeTaken = (Date.now() - startTime) / 1000;
        const base = q.points || 100;
        const earned = isCorrect ? base + (timeTaken <= 30 ? 15 : 0) : 0;

        touchStreak();
        setSessionScore(s => s + earned);
        setAllTimeScore(s => s + earned);
        setSessionAnswers(prev => [...prev, {
            question: q.question,
            code_snippet: q.code_snippet,
            selected,
            correct: q.correct_answer,
            explanation: q.explanation,
            isCorrect,
            earned,
        }]);
        setAnswered(true);
    };

    // ── Go to next question or score screen ───────────────────────────────
    const nextQuestion = () => {
        if (current + 1 >= questions.length) {
            setView(VIEW.SCORE);
        } else {
            setCurrent(i => i + 1);
            setSelected('');
            setAnswered(false);
            setStartTime(Date.now());
        }
    };

    const gameInfo = GAME_CARDS.find(g => g.id === gameType);
    const q = questions[current] || {};

    // ───────────────────────────────────────────────────────────────────────
    // RENDER: Score Screen
    // ───────────────────────────────────────────────────────────────────────
    if (view === VIEW.SCORE) {
        const correct = sessionAnswers.filter(a => a.isCorrect).length;
        const accuracy = Math.round((correct / sessionAnswers.length) * 100);
        const passed = accuracy >= 60;
        return (
            <PageContainer>
                {/* Score header */}
                <Box sx={{ textAlign: 'center', mb: 4 }}>
                    <Typography fontSize={64} lineHeight={1} mb={1}>{passed ? '🏆' : '💪'}</Typography>
                    <Typography variant="h4" fontWeight={900}>{passed ? 'Great Job!' : 'Keep Practising!'}</Typography>
                    <Typography color="text.secondary" mt={0.5}>
                        Concept: <b>{session?.concept?.replace(/_/g, ' ')}</b>
                        {session?.rag_chunks_used > 0 && (
                            <Chip
                                label={`RAG: ${session.rag_chunks_used} chunks used`}
                                size="small"
                                sx={{ ml: 1.5, bgcolor: '#e8f5e9', color: '#2e7d32', fontWeight: 700, fontSize: '0.72rem' }}
                            />
                        )}
                    </Typography>
                </Box>

                {/* Score stats */}
                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mb: 5, flexWrap: 'wrap' }}>
                    {[
                        { label: 'Score', value: `${sessionScore} pts`, color: '#1976d2' },
                        { label: 'Accuracy', value: `${accuracy}%`, color: accuracy >= 60 ? '#4caf50' : '#f44336' },
                        { label: 'Correct', value: `${correct} / ${sessionAnswers.length}`, color: '#ff9800' },
                        { label: 'Streak 🔥', value: `${streak} days`, color: '#e65100' },
                    ].map(stat => (
                        <Box key={stat.label} sx={{
                            textAlign: 'center', p: 2.5, minWidth: 110, bgcolor: 'background.paper',
                            borderRadius: 3, border: '1px solid', borderColor: 'divider',
                            boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                        }}>
                            <Typography variant="h5" fontWeight={900} color={stat.color}>{stat.value}</Typography>
                            <Typography variant="caption" color="text.secondary" textTransform="uppercase" fontWeight={700}>{stat.label}</Typography>
                        </Box>
                    ))}
                </Box>

                {/* Per-question review */}
                <Typography variant="h6" fontWeight={800} mb={2}>📋 Question Review</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 4 }}>
                    {sessionAnswers.map((a, i) => (
                        <Box key={i} sx={{
                            p: 2.5, borderRadius: 2, border: '2px solid',
                            borderColor: a.isCorrect ? '#c8e6c9' : '#ffcdd2',
                            bgcolor: a.isCorrect ? '#f9fbe7' : '#fff8f8',
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                                {a.isCorrect
                                    ? <CheckCircle sx={{ color: '#4caf50', mt: 0.3 }} />
                                    : <Cancel sx={{ color: '#f44336', mt: 0.3 }} />}
                                <Box flex={1}>
                                    <Typography fontWeight={700} mb={0.5}>Q{i + 1}: {a.question}</Typography>
                                    {a.code_snippet && (
                                        <Box sx={{ bgcolor: '#1e1e1e', color: '#e4e4e4', p: 1.5, borderRadius: 1.5, fontFamily: 'monospace', fontSize: 12, mb: 1, whiteSpace: 'pre-wrap' }}>
                                            {a.code_snippet}
                                        </Box>
                                    )}
                                    <Typography variant="body2" color="text.secondary">
                                        Your answer: <b>{a.selected}</b>
                                        {!a.isCorrect && <> · Correct: <b style={{ color: '#4caf50' }}>{a.correct}</b></>}
                                        {a.earned > 0 && <Chip label={`+${a.earned} pts`} size="small" sx={{ ml: 1, bgcolor: '#e8f5e9', color: '#2e7d32', fontWeight: 700 }} />}
                                    </Typography>
                                    <Typography variant="body2" sx={{ mt: 0.75, color: '#555' }}>
                                        💡 {a.explanation}
                                    </Typography>
                                </Box>
                            </Box>
                        </Box>
                    ))}
                </Box>

                {/* CTA buttons */}
                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
                    <Button
                        variant="contained" startIcon={<Replay />}
                        onClick={() => startSession(gameType)}
                        sx={{ borderRadius: 2, fontWeight: 700, px: 4, bgcolor: gameInfo?.color, '&:hover': { filter: 'brightness(0.9)', bgcolor: gameInfo?.color } }}
                    >
                        Play Again
                    </Button>
                    <Button variant="outlined" onClick={() => setView(VIEW.LOBBY)} sx={{ borderRadius: 2, fontWeight: 700 }}>
                        Choose Another Game
                    </Button>
                    <Button variant="outlined" onClick={() => navigate('/submit')} startIcon={<SportsEsports />} sx={{ borderRadius: 2, fontWeight: 700 }}>
                        Submit Code for Review
                    </Button>
                </Box>
            </PageContainer>
        );
    }

    // ───────────────────────────────────────────────────────────────────────
    // RENDER: Question Screen
    // ───────────────────────────────────────────────────────────────────────
    if (view === VIEW.QUESTION) {
        const progress = ((current) / questions.length) * 100;
        return (
            <PageContainer>
                {/* Header bar */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Typography fontSize={28}>{gameInfo?.icon}</Typography>
                        <Box>
                            <Typography variant="h6" fontWeight={800} lineHeight={1}>{gameInfo?.title}</Typography>
                            <Typography variant="caption" color="text.secondary">
                                Concept: <b>{session?.concept?.replace(/_/g, ' ') || 'general'}</b>
                                {session?.rag_chunks_used > 0 && (
                                    <Chip
                                        label={`🔍 ${session.rag_chunks_used} RAG chunks`}
                                        size="small"
                                        sx={{ ml: 1, bgcolor: '#e3f2fd', color: '#1565c0', fontWeight: 700, fontSize: '0.68rem' }}
                                    />
                                )}
                            </Typography>
                        </Box>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="h6" fontWeight={800} color="primary.main">{sessionScore} pts</Typography>
                        <Typography variant="caption" color="text.secondary">Question {current + 1} / {questions.length}</Typography>
                    </Box>
                </Box>

                {/* Progress bar */}
                <LinearProgress
                    variant="determinate" value={progress}
                    sx={{ height: 8, borderRadius: 4, mb: 3, bgcolor: '#e3f2fd', '& .MuiLinearProgress-bar': { bgcolor: gameInfo?.color } }}
                />

                {/* Question card */}
                <Card sx={{ borderRadius: 3, border: '1px solid', borderColor: 'divider', mb: 3 }}>
                    <CardContent sx={{ p: 3 }}>
                        <Typography variant="h6" fontWeight={700} mb={2} lineHeight={1.5}>{q.question}</Typography>

                        {q.code_snippet && (
                            <Box sx={{
                                bgcolor: '#1e1e1e', color: '#e4e4e4', p: 2.5, borderRadius: 2, mb: 3,
                                fontFamily: '"Fira Code", monospace', fontSize: 13.5, whiteSpace: 'pre-wrap',
                                overflowX: 'auto', border: '1px solid #333',
                            }}>
                                {q.code_snippet}
                            </Box>
                        )}

                        <Typography variant="subtitle2" color="text.secondary" fontWeight={600} mb={1.5} textTransform="uppercase" fontSize="0.72rem">
                            Select your answer:
                        </Typography>

                        <RadioGroup value={selected} onChange={e => !answered && setSelected(e.target.value)}>
                            {(q.options || []).map((opt, i) => {
                                const optId = opt.charAt(0);
                                const isCorrectOpt = optId === q.correct_answer;
                                const isSelectedOpt = optId === selected;
                                let border = 'divider'; let bg = 'transparent';
                                if (answered) {
                                    if (isCorrectOpt) { border = '#4caf50'; bg = '#f1f8e9'; }
                                    else if (isSelectedOpt) { border = '#f44336'; bg = '#ffebee'; }
                                } else if (isSelectedOpt) { border = 'primary.main'; bg = '#e3f2fd'; }

                                return (
                                    <FormControlLabel
                                        key={i} value={optId}
                                        control={<Radio color={answered ? (isCorrectOpt ? 'success' : 'error') : 'primary'} sx={{ display: answered ? 'none' : 'inline-flex' }} />}
                                        label={<Typography fontWeight={isSelectedOpt || (answered && isCorrectOpt) ? 700 : 500}>{opt}</Typography>}
                                        sx={{
                                            margin: 0, mb: 1.5, px: 2, py: 1.5, borderRadius: 2, border: '2px solid',
                                            borderColor: border, bgcolor: bg, transition: 'all .18s',
                                            '&:hover': !answered ? { borderColor: 'primary.light', bgcolor: 'action.hover' } : {},
                                        }}
                                    />
                                );
                            })}
                        </RadioGroup>

                        {/* Post-answer feedback */}
                        {answered && (
                            <Box sx={{ mt: 2.5, animation: 'fadeIn 0.4s', '@keyframes fadeIn': { from: { opacity: 0 }, to: { opacity: 1 } } }}>
                                {selected === q.correct_answer ? (
                                    <Alert severity="success" icon={<CheckCircle />} sx={{ borderRadius: 2 }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.25 }}>
                                            <Typography fontWeight={800}>Correct! 🎉</Typography>
                                            <Typography fontWeight={700} color="success.main">
                                                +{q.points || 100}{((Date.now() - startTime) / 1000) <= 30 ? ' +15 Fast Bonus ⚡' : ''} pts
                                            </Typography>
                                        </Box>
                                        <Typography variant="body2">{q.explanation}</Typography>
                                    </Alert>
                                ) : (
                                    <Box sx={{ p: 2, bgcolor: '#fff3e0', borderRadius: 2, border: '1px solid #ffcc80' }}>
                                        <Typography variant="subtitle2" fontWeight={800} color="#e65100" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                            <AutoAwesome fontSize="small" /> AI Mentor Insight
                                        </Typography>
                                        <Typography variant="body2">{q.explanation}</Typography>
                                        {q.hint && (
                                            <>
                                                <Divider sx={{ my: 1.5, borderColor: '#ffcc80' }} />
                                                <Typography variant="body2">
                                                    <b>Hint:</b> {q.hint}
                                                </Typography>
                                            </>
                                        )}
                                    </Box>
                                )}
                            </Box>
                        )}
                    </CardContent>
                </Card>

                {/* Action buttons */}
                <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                    <Button variant="outlined" onClick={() => setView(VIEW.LOBBY)} sx={{ borderRadius: 2, fontWeight: 700 }}>Exit</Button>
                    {!answered ? (
                        <Button
                            variant="contained" disabled={!selected}
                            onClick={handleSubmit}
                            sx={{ borderRadius: 2, fontWeight: 700, px: 4, bgcolor: gameInfo?.color, '&:hover': { filter: 'brightness(0.9)', bgcolor: gameInfo?.color } }}
                        >
                            Check Answer
                        </Button>
                    ) : (
                        <Button
                            variant="contained" onClick={nextQuestion} endIcon={current + 1 >= questions.length ? <EmojiEvents /> : null}
                            sx={{ borderRadius: 2, fontWeight: 700, px: 4, bgcolor: gameInfo?.color, '&:hover': { filter: 'brightness(0.9)', bgcolor: gameInfo?.color } }}
                        >
                            {current + 1 >= questions.length ? 'See Results 🏆' : 'Next Question →'}
                        </Button>
                    )}
                </Box>
            </PageContainer>
        );
    }

    // ───────────────────────────────────────────────────────────────────────
    // RENDER: Loading Screen
    // ───────────────────────────────────────────────────────────────────────
    if (view === VIEW.LOADING) {
        return (
            <PageContainer>
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 3 }}>
                    <CircularProgress size={56} thickness={4} sx={{ color: gameInfo?.color }} />
                    <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="h6" fontWeight={700} mb={0.5}>Generating 5 Questions…</Typography>
                        <Typography color="text.secondary">
                            Searching your knowledge base and calling Gemini AI
                        </Typography>
                    </Box>
                    <LinearProgress sx={{ width: 280, borderRadius: 4, height: 6 }} />
                </Box>
            </PageContainer>
        );
    }

    // ───────────────────────────────────────────────────────────────────────
    // RENDER: Lobby (default)
    // ───────────────────────────────────────────────────────────────────────
    const accuracy = allTimeScore > 0 ? Math.min(99, Math.round((allTimeScore / Math.max(1, allTimeScore + 50)) * 100)) : 0;

    return (
        <PageContainer>
            {/* Header */}
            <Box sx={{ mb: 4 }}>
                <Typography variant="h5" fontWeight={800} gutterBottom>🎮 Coding Games</Typography>
                <Typography variant="body2" color="text.secondary" mb={3}>
                    5 AI-generated questions targeting your weakest concept · RAG-powered
                </Typography>

                {/* Stats bar */}
                <Box sx={{ display: 'flex', gap: 2, p: 2, bgcolor: 'background.paper', borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.06)', border: '1px solid', borderColor: 'divider', maxWidth: 400 }}>
                    {[
                        { label: 'Score', value: `${allTimeScore} pts`, color: 'primary.main', icon: null },
                        { label: 'Streak', value: `${streak}🔥`, color: '#e65100', icon: null },
                        { label: 'Progress', value: `${accuracy}%`, color: '#4caf50', icon: null },
                    ].map((stat, i) => (
                        <Box key={i} sx={{ flex: 1, textAlign: 'center' }}>
                            <Typography variant="h6" fontWeight={800} color={stat.color}>{stat.value}</Typography>
                            <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase">{stat.label}</Typography>
                        </Box>
                    ))}
                </Box>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>}

            {/* Game cards */}
            <Grid container spacing={3}>
                {GAME_CARDS.map(game => (
                    <Grid item xs={12} sm={6} md={4} key={game.id}>
                        <Card sx={{
                            borderRadius: 3, height: '100%', display: 'flex', flexDirection: 'column',
                            transition: 'all .25s cubic-bezier(0.4, 0, 0.2, 1)', border: '1px solid', borderColor: 'divider',
                            '&:hover': { transform: 'translateY(-4px)', boxShadow: `0 12px 32px ${game.color}20`, borderColor: `${game.color}50` },
                        }}>
                            <CardContent sx={{ p: 3, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                    <Typography fontSize={40} lineHeight={1}>{game.icon}</Typography>
                                    <Chip label={game.diff} size="small" sx={{ bgcolor: `${game.color}15`, color: game.color, fontWeight: 700 }} />
                                </Box>
                                <Typography variant="h6" fontWeight={700} gutterBottom>{game.title}</Typography>

                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2.5, mt: 0.5 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
                                        <AccessTime fontSize="small" sx={{ opacity: 0.7 }} />
                                        <Typography variant="body2" fontWeight={500}>{game.time} · 5 questions</Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
                                        <CrisisAlert fontSize="small" sx={{ opacity: 0.7 }} />
                                        <Typography variant="body2" fontWeight={500}>{game.skill}</Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
                                        <AutoAwesome fontSize="small" sx={{ opacity: 0.7, color: '#1976d2' }} />
                                        <Typography variant="body2" fontWeight={500} color="#1565c0">RAG + Gemini powered</Typography>
                                    </Box>
                                </Box>

                                <Box sx={{ mt: 'auto', pt: 2 }}>
                                    <Button
                                        variant="contained" fullWidth
                                        onClick={() => startSession(game.id)}
                                        sx={{ bgcolor: game.color, color: '#fff', fontWeight: 700, borderRadius: 2, py: 1, '&:hover': { bgcolor: game.color, filter: 'brightness(0.9)' } }}
                                    >
                                        Start 5-Question Challenge
                                    </Button>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {/* CTA banner */}
            <Box sx={{ textAlign: 'center', mt: 6, p: 4, bgcolor: '#e3f2fd', borderRadius: 3, border: '1px solid #bbdefb' }}>
                <Typography variant="h6" fontWeight={800} color="#1565c0" gutterBottom>🏆 Ready for a bigger challenge?</Typography>
                <Typography variant="body2" color="text.secondary" mb={3}>
                    Submit real code to get personalized AI feedback and discover your blind spots.
                </Typography>
                <Button variant="contained" startIcon={<SportsEsports />} onClick={() => navigate('/submit')} sx={{ borderRadius: 2, fontWeight: 700, px: 3 }}>
                    Submit Code for AI Review
                </Button>
            </Box>
        </PageContainer>
    );
}
