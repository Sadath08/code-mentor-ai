import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Button, Card, CardContent, Divider, Chip,
    Table, TableBody, TableCell, TableHead, TableRow, TableContainer,
    Paper, LinearProgress, Alert, IconButton, CircularProgress
} from '@mui/material';
import {
    CloudUpload as CloudUploadIcon,
    Delete as DeleteIcon,
    Refresh as RefreshIcon,
    MenuBook as MenuBookIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function KnowledgeBase() {
    const [documents, setDocuments] = useState([]);
    const [ragStatus, setRagStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const fetchData = async () => {
        setLoading(true);
        setError("");
        try {
            const [docsRes, statusRes] = await Promise.all([
                axios.get(`${API_BASE}/api/documents/`),
                axios.get(`${API_BASE}/api/documents/rag-status`).catch(() => null)
            ]);
            setDocuments(docsRes.data);
            if (statusRes) {
                setRagStatus(statusRes.data);
            }
        } catch (err) {
            setError("Failed to fetch knowledge base data. Is the backend running?");
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploading(true);
        setError("");
        setSuccess("");

        const formData = new FormData();
        formData.append("file", file);
        formData.append("language", "general"); // Could let user select this

        try {
            await axios.post(`${API_BASE}/api/documents/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setSuccess(`Successfully uploaded and indexed ${file.name}`);
            fetchData(); // Refresh lists
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to upload document");
        } finally {
            setUploading(false);
            // reset file input
            event.target.value = null;
        }
    };

    const handleDelete = async (id, filename) => {
        if (!window.confirm(`Are you sure you want to remove ${filename} from the database? (Note: Vectors are not removed from the current index until a rebuild)`)) {
            return;
        }

        try {
            await axios.delete(`${API_BASE}/api/documents/${id}`);
            fetchData();
        } catch (err) {
            setError("Failed to delete document");
        }
    };

    return (
        <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1200, mx: 'auto' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight={800} color="#0f172a" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <MenuBookIcon fontSize="large" color="primary" />
                        Knowledge Base
                    </Typography>
                    <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
                        Manage custom documents that power the AI's RAG system.
                    </Typography>
                </Box>

                <Button
                    variant="contained"
                    component="label"
                    startIcon={uploading ? <CircularProgress size={20} color="inherit" /> : <CloudUploadIcon />}
                    disabled={uploading}
                    sx={{ borderRadius: 2, px: 3, py: 1.5, fontWeight: 700, background: 'linear-gradient(90deg, #10b981, #3b82f6)' }}
                >
                    {uploading ? 'Uploading...' : 'Upload Document'}
                    <input type="file" hidden accept=".pdf,.doc,.docx,.txt,.md,.py,.js,.jsx,.ts,.tsx,.java,.cpp" onChange={handleFileUpload} />
                </Button>
            </Box>

            {error && <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>}
            {success && <Alert severity="success" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setSuccess("")}>{success}</Alert>}

            {/* RAG Status Overview */}
            <Card sx={{ mb: 4, borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
                <CardContent sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6" fontWeight={700} color="#1e293b">Engine Status</Typography>
                        <IconButton onClick={fetchData} size="small" disabled={loading}><RefreshIcon /></IconButton>
                    </Box>
                    <Divider sx={{ mb: 2 }} />

                    {loading && !ragStatus ? (
                        <LinearProgress sx={{ borderRadius: 1 }} />
                    ) : ragStatus ? (
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                            <Box>
                                <Typography variant="body2" color="text.secondary">Mode</Typography>
                                <Chip
                                    label={ragStatus.mode === 'live' ? 'Live (FAISS)' : 'Fallback (Static)'}
                                    color={ragStatus.mode === 'live' ? 'success' : 'warning'}
                                    size="small"
                                    sx={{ mt: 0.5, fontWeight: 600 }}
                                />
                            </Box>
                            <Box>
                                <Typography variant="body2" color="text.secondary">Vectors Indexed</Typography>
                                <Typography variant="h6" fontWeight={700} color="#0f172a">{ragStatus.vectors.toLocaleString()}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="body2" color="text.secondary">Index Type</Typography>
                                <Typography variant="h6" fontWeight={700} color="#0f172a">{ragStatus.index_type}</Typography>
                            </Box>
                        </Box>
                    ) : (
                        <Typography color="text.secondary">Status unavailable</Typography>
                    )}
                </CardContent>
            </Card>

            {/* Documents List */}
            <Typography variant="h6" fontWeight={700} color="#1e293b" sx={{ mb: 2 }}>
                Uploaded Documents
            </Typography>

            <TableContainer component={Paper} sx={{ borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
                <Table>
                    <TableHead sx={{ bgcolor: '#f8fafc' }}>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 600, color: '#475569' }}>Filename</TableCell>
                            <TableCell sx={{ fontWeight: 600, color: '#475569' }}>Type</TableCell>
                            <TableCell sx={{ fontWeight: 600, color: '#475569' }}>Status</TableCell>
                            <TableCell sx={{ fontWeight: 600, color: '#475569' }}>Chunks</TableCell>
                            <TableCell sx={{ fontWeight: 600, color: '#475569' }}>Uploaded</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 600, color: '#475569' }}>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {loading && documents.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                                    <CircularProgress size={30} />
                                </TableCell>
                            </TableRow>
                        ) : documents.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={6} align="center" sx={{ py: 4, color: '#64748b' }}>
                                    No custom documents uploaded yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            documents.map((doc) => (
                                <TableRow key={doc.id} hover>
                                    <TableCell sx={{ fontWeight: 500, color: '#0f172a' }}>{doc.filename}</TableCell>
                                    <TableCell>
                                        <Chip label={doc.file_type.toUpperCase()} size="small" variant="outlined" sx={{ borderRadius: 1 }} />
                                    </TableCell>
                                    <TableCell>
                                        <Chip
                                            label={doc.status}
                                            color={doc.status === 'indexed' ? 'success' : doc.status === 'error' ? 'error' : 'warning'}
                                            size="small"
                                            sx={{ borderRadius: 1, fontWeight: 600, fontSize: '0.75rem' }}
                                        />
                                    </TableCell>
                                    <TableCell>{doc.chunk_count}</TableCell>
                                    <TableCell>{new Date(doc.uploaded_at).toLocaleDateString()}</TableCell>
                                    <TableCell align="right">
                                        <IconButton size="small" color="error" onClick={() => handleDelete(doc.id, doc.filename)}>
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    );
}
