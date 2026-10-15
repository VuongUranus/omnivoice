#!/usr/bin/env python3
"""
OmniVoice Studio - Web UI (v4)
Includes:
1. Voice Selection Modal & Compact Voice Preview Card in Settings (Image 1 & 2)
2. Persistent Bottom Player Dock with auto-play & auto-switch to History on generate (Image 3)
3. Dedicated Full-Page Voice Creator / Voice Cloning View (Image 4)
Runs on the local OmniVoice model (Apple Silicon MPS / CUDA / CPU).
"""

import os
import time
import uuid
import json
import argparse
import logging
from datetime import datetime
import gradio as gr
import numpy as np
import soundfile as sf
import torch

from omnivoice import OmniVoice, OmniVoiceGenerationConfig
from omnivoice.utils.common import get_best_device
from omnivoice.utils.lang_map import LANG_NAMES, lang_display_name

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_DIR = os.path.join(SCRIPT_DIR, "presets")
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
HISTORY_INDEX = os.path.join(HISTORY_DIR, "history.json")
CUSTOM_VOICES_DIR = os.path.join(SCRIPT_DIR, "custom_voices")
CUSTOM_VOICES_FILE = os.path.join(CUSTOM_VOICES_DIR, "custom_voices.json")
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(CUSTOM_VOICES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Preset Voices Definition (Matching UI Designs)
# ---------------------------------------------------------------------------
PRESET_VOICES = {
    "🚀 PEAKTV - Documentary, Tech, Low Pitch": {
        "name": "PEAKTV",
        "audio": os.path.join(PRESETS_DIR, "elon_musk_7s.wav"),
        "audio_url": f"/gradio_api/file={os.path.join(PRESETS_DIR, 'elon_musk_7s.wav')}",
        "ref_text": "Elon Musk bắt đầu đưa ra những lời tuyên bố đầy tham vọng, nhắm thẳng vào mẫu xe bán tải bán chạy nhất nước Mỹ suốt nhiều thập kỷ qua.",
        "avatar": "🚀",
        "style_tag": "Documentary, Tech",
        "desc": "Giọng nam trầm ấm, đĩnh đạc và lôi cuốn, chuyên dụng cho phim tài liệu khoa học và công nghệ.",
        "tags": ["Tiếng Việt", "Documentary", "Tech", "Nam", "Trầm ấm"],
        "grad": "linear-gradient(135deg, #6366f1, #8b5cf6)",
        "instruct": "male, low pitch, young adult, documentary",
    },
    "✈️ Pavel Durov - Narrative, Calm, Serious": {
        "name": "Pavel Durov",
        "audio": os.path.join(PRESETS_DIR, "pavel_durov_8s.wav"),
        "audio_url": f"/gradio_api/file={os.path.join(PRESETS_DIR, 'pavel_durov_8s.wav')}",
        "ref_text": "Trong khi nhiều tỷ phú chọn sống giữa siêu du thuyền, tiệc xa hoa, rượu đắt và các thú vui hưởng thụ, Durov lại đi theo con đường ngược lại.",
        "avatar": "✈️",
        "style_tag": "Narrative, Calm",
        "desc": "Âm sắc điềm đạm, triết lý, phong cách tối giản và bí ẩn, thích hợp cho podcast và tiểu sử.",
        "tags": ["Tiếng Việt", "Narrative", "Nam", "Podcast", "Triết lý"],
        "grad": "linear-gradient(135deg, #0ea5e9, #06b6d4)",
        "instruct": "male, low pitch, middle-aged, narrative",
    },
    "💰 Tôi là Lóng - Finance, Casual, Analytical": {
        "name": "Tôi là Lóng",
        "audio": os.path.join(PRESETS_DIR, "cashback_8s.wav"),
        "audio_url": f"/gradio_api/file={os.path.join(PRESETS_DIR, 'cashback_8s.wav')}",
        "ref_text": "Dù là vậy thì nghiên cứu từ cái lĩnh vực kinh tế học hành vi chỉ ra rằng là cashback có khả năng thay đổi nhận thức của người tiêu dùng.",
        "avatar": "💰",
        "style_tag": "Finance, Analytical",
        "desc": "Giọng đọc phân tích kinh tế thực tế, nhịp điệu sinh động và tự nhiên, rất hút người nghe.",
        "tags": ["Tiếng Việt", "Finance", "Nam", "Tin tức", "Tự nhiên"],
        "grad": "linear-gradient(135deg, #f59e0b, #f97316)",
        "instruct": "male, moderate pitch, young adult, analytical",
    },
    "🎙️ Tùy chỉnh (Tải lên file mẫu riêng...)": {
        "name": "Custom Voice",
        "audio": None,
        "audio_url": "",
        "ref_text": "",
        "avatar": "🎙️",
        "style_tag": "Custom Upload",
        "desc": "Tải lên file âm thanh mẫu của chính bạn để clone giọng nói tức thì.",
        "tags": ["Tùy chỉnh", "Custom"],
        "grad": "linear-gradient(135deg, #64748b, #334155)",
        "instruct": "",
    },
}

_ALL_LANGUAGES = ["Auto"] + sorted(lang_display_name(n) for n in LANG_NAMES)

# ---------------------------------------------------------------------------
# JavaScript Controller (Theme, Navigation, Modal, Bottom Player, History)
# ---------------------------------------------------------------------------
OMNIVOICE_THEME_JS = """
() => {
    // 1. Theme Management (Light & Dark)
    function applyTheme(isDark) {
        if (isDark) {
            document.documentElement.classList.add('dark');
            document.body.classList.add('dark');
            const gApp = document.querySelector('gradio-app');
            if (gApp) gApp.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
            document.body.classList.remove('dark');
            const gApp = document.querySelector('gradio-app');
            if (gApp) gApp.classList.remove('dark');
        }
        updateToggleButtons(isDark);
    }

    function updateToggleButtons(isDark) {
        document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            const ico = btn.querySelector('.theme-btn-ico');
            const txt = btn.querySelector('.theme-btn-txt');
            if (ico) ico.textContent = isDark ? '☀️' : '🌙';
            if (txt) txt.textContent = isDark ? 'Light' : 'Dark';
        });
        document.querySelectorAll('.theme-nav-toggle').forEach(item => {
            const ico = item.querySelector('.theme-nav-ico');
            const txt = item.querySelector('.theme-nav-txt');
            if (ico) ico.textContent = isDark ? '☀️' : '🌙';
            if (txt) txt.textContent = isDark ? 'Chế độ sáng' : 'Chế độ tối';
        });
    }

    const urlObj = new URL(window.location);
    let currentDarkState = false;

    try {
        const paramTheme = urlObj.searchParams.get('theme') || urlObj.searchParams.get('__theme');
        if (paramTheme === 'dark') {
            currentDarkState = true;
        } else if (paramTheme === 'light') {
            currentDarkState = false;
        } else {
            const saved = localStorage.getItem('omnivoice_theme');
            if (saved) {
                currentDarkState = (saved === 'dark');
            } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                currentDarkState = true;
            }
        }
    } catch(e){}

    window.toggleOmniVoiceTheme = function() {
        currentDarkState = !document.documentElement.classList.contains('dark');
        try { localStorage.setItem('omnivoice_theme', currentDarkState ? 'dark' : 'light'); } catch(e){}
        applyTheme(currentDarkState);
    };

    applyTheme(currentDarkState);

    // 2. Page Navigation & Tab Switching
    window.switchSettingsTab = function(tabName) {
        const tablist = document.querySelector('.settings-col [role="tablist"]');
        if (tablist) {
            const tab = Array.from(tablist.querySelectorAll('button[role="tab"], button')).find(b => b.textContent.trim().toLowerCase().includes(tabName.toLowerCase()));
            if (tab) {
                tab.click();
                return;
            }
        }
        const btns = Array.from(document.querySelectorAll('.settings-col button[role="tab"], .settings-col button'));
        const target = btns.find(b => b.textContent.trim().toLowerCase().includes(tabName.toLowerCase()));
        if (target) {
            target.click();
        }
    };

    window.switchOmniVoicePage = function(page) {
        const pageTts = document.getElementById('page-tts');
        const pageCreator = document.getElementById('page-creator');
        const navTts = document.getElementById('nav-item-tts');
        const navCreator = document.getElementById('nav-item-creator');
        const navHistory = document.getElementById('nav-item-history');

        if (navTts) navTts.classList.remove('active');
        if (navCreator) navCreator.classList.remove('active');
        if (navHistory) navHistory.classList.remove('active');

        if (page === 'creator') {
            if (pageTts) {
                pageTts.classList.remove('active');
                pageTts.style.setProperty('display', 'none', 'important');
            }
            if (pageCreator) {
                pageCreator.classList.add('active');
                pageCreator.style.setProperty('display', 'flex', 'important');
            }
            if (navCreator) navCreator.classList.add('active');
        } else if (page === 'history') {
            if (pageCreator) {
                pageCreator.classList.remove('active');
                pageCreator.style.setProperty('display', 'none', 'important');
            }
            if (pageTts) {
                pageTts.classList.add('active');
                pageTts.style.setProperty('display', 'flex', 'important');
            }
            if (navHistory) navHistory.classList.add('active');
            setTimeout(() => {
                window.switchSettingsTab('history');
            }, 60);
        } else { // 'tts'
            if (pageCreator) {
                pageCreator.classList.remove('active');
                pageCreator.style.setProperty('display', 'none', 'important');
            }
            if (pageTts) {
                pageTts.classList.add('active');
                pageTts.style.setProperty('display', 'flex', 'important');
            }
            if (navTts) navTts.classList.add('active');
        }
    };

    // 3. Voice Selection Modal (Requirement 1: Image 2)
    window.openVoiceModal = function() {
        const modal = document.getElementById('voice-modal-overlay');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            const searchInput = document.getElementById('vm-search-input');
            if (searchInput) {
                searchInput.value = '';
                searchInput.focus();
            }
            window.filterVoiceModal();
        }
    };

    window.closeVoiceModal = function() {
        const modal = document.getElementById('voice-modal-overlay');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
        if (window._modalPreviewAudio) {
            window._modalPreviewAudio.pause();
            document.querySelectorAll('.vm-card-art-play').forEach(p => p.textContent = '▶');
        }
    };

    window.switchModalTab = function(tabName) {
        document.querySelectorAll('.vm-tab').forEach(t => t.classList.remove('active'));
        const activeTabBtn = document.getElementById('vm-tab-' + tabName);
        if (activeTabBtn) activeTabBtn.classList.add('active');

        window._activeModalTab = tabName;
        window.filterVoiceModal();
    };

    window.filterVoiceTag = function(tag, btn) {
        document.querySelectorAll('.vm-chip').forEach(c => c.classList.remove('active'));
        if (btn) btn.classList.add('active');
        window._activeModalTag = tag.toLowerCase();
        window.filterVoiceModal();
    };

    window.filterVoiceModal = function() {
        const q = (document.getElementById('vm-search-input')?.value || '').toLowerCase().trim();
        const activeTag = window._activeModalTag || 'all';
        const activeTab = window._activeModalTab || 'library';

        document.querySelectorAll('.vm-voice-row').forEach(row => {
            const cardTab = row.getAttribute('data-tab') || 'library';
            const name = (row.getAttribute('data-name') || '').toLowerCase();
            const desc = (row.getAttribute('data-desc') || '').toLowerCase();
            const tags = (row.getAttribute('data-tags') || '').toLowerCase();

            const tabMatch = (activeTab === 'all' || activeTab === 'collected' || cardTab === activeTab);
            const tagMatch = (activeTag === 'all' || tags.includes(activeTag) || name.includes(activeTag));
            const queryMatch = (!q || name.includes(q) || desc.includes(q) || tags.includes(q));

            if (tabMatch && tagMatch && queryMatch) {
                row.style.display = 'flex';
            } else {
                row.style.display = 'none';
            }
        });
    };

    window.playVoiceModalSample = function(audioUrl, event) {
        if (event) event.stopPropagation();
        if (!audioUrl) return;

        if (!window._modalPreviewAudio) {
            window._modalPreviewAudio = new Audio();
            window._modalPreviewAudio.addEventListener('ended', () => {
                document.querySelectorAll('.vm-card-art-play').forEach(p => p.textContent = '▶');
            });
        }

        const btn = event ? event.currentTarget.querySelector('.vm-card-art-play') : null;

        if (window._modalPreviewAudio.src.endsWith(audioUrl) && !window._modalPreviewAudio.paused) {
            window._modalPreviewAudio.pause();
            if (btn) btn.textContent = '▶';
        } else {
            document.querySelectorAll('.vm-card-art-play').forEach(p => p.textContent = '▶');
            window._modalPreviewAudio.src = audioUrl;
            window._modalPreviewAudio.play().then(() => {
                if (btn) btn.textContent = '⏸';
            }).catch(e => console.log(e));
        }
    };

    window.selectVoiceFromModal = function(voiceKey) {
        const bridge = document.querySelector('#voice-bridge-input textarea, #voice-bridge-input input');
        if (bridge) {
            bridge.value = voiceKey;
            bridge.dispatchEvent(new Event('input', { bubbles: true }));
            bridge.dispatchEvent(new Event('change', { bubbles: true }));
        }
        window.updateVoiceCardDirectly(voiceKey);
        window.closeVoiceModal();
    };

    window.resetVoiceToDefault = function() {
        const firstVoiceKey = window._defaultFirstVoice || '🚀 PEAKTV - Documentary, Tech, Low Pitch';
        window.selectVoiceFromModal(firstVoiceKey);
    };

    window.toggleCurrentVoiceSample = function(event) {
        if (event) event.stopPropagation();
        const currentAudioUrl = window._currentVoiceAudioUrl;
        if (!currentAudioUrl) return;

        if (!window._voiceCardAudio) {
            window._voiceCardAudio = new Audio();
            window._voiceCardAudio.addEventListener('ended', () => {
                const icon = document.getElementById('vpc-play-ico');
                if (icon) icon.textContent = '▶';
            });
        }

        const icon = document.getElementById('vpc-play-ico');
        if (window._voiceCardAudio.src.endsWith(currentAudioUrl) && !window._voiceCardAudio.paused) {
            window._voiceCardAudio.pause();
            if (icon) icon.textContent = '▶';
        } else {
            window._voiceCardAudio.src = currentAudioUrl;
            window._voiceCardAudio.play().then(() => {
                if (icon) icon.textContent = '⏸';
            }).catch(e => console.log(e));
        }
    };

    window.updateVoiceCardDirectly = function(voiceKey) {
        let name = 'PEAKTV', styleTag = 'Documentary, Tech', grad = 'linear-gradient(135deg, #6366f1, #8b5cf6)', audioUrl = '', avatar = '🎙️';
        const row = document.querySelector(`.vm-voice-row[data-key="${voiceKey}"]`);
        if (row) {
            name = row.getAttribute('data-name') || name;
            styleTag = row.getAttribute('data-style') || styleTag;
            grad = row.getAttribute('data-grad') || grad;
            audioUrl = row.getAttribute('data-audio') || '';
        }

        window._currentVoiceAudioUrl = audioUrl;

        const nameEl = document.getElementById('vpc-name');
        const subEl = document.getElementById('vpc-sub');
        const thumbEl = document.getElementById('vpc-thumb');
        if (nameEl) nameEl.textContent = name;
        if (subEl) subEl.textContent = styleTag;
        if (thumbEl && grad) thumbEl.style.background = grad;

        const pillNm = document.querySelector('.voice-chip .nm');
        const pillTg = document.querySelector('.voice-chip .tg');
        const pillAv = document.querySelector('.voice-chip .av');
        if (pillNm) pillNm.textContent = name;
        if (pillTg) pillTg.textContent = '· ' + styleTag;
        if (pillAv && grad) pillAv.style.background = grad;
    };

    setTimeout(() => {
        const firstRow = document.querySelector('.vm-voice-row');
        if (firstRow) {
            window._currentVoiceAudioUrl = firstRow.getAttribute('data-audio') || '';
            window._defaultFirstVoice = firstRow.getAttribute('data-key') || '';
        }
    }, 250);

    window.selectVoiceAndGoToTTS = function(voiceKey) {
        window.selectVoiceFromModal(voiceKey);
        window.switchOmniVoicePage('tts');
    };

    // 4. Persistent Bottom Player Bar (Requirement 2: Image 3)
    let bottomAudio = document.getElementById('omni-bottom-audio-native');
    if (!bottomAudio) {
        bottomAudio = document.createElement('audio');
        bottomAudio.id = 'omni-bottom-audio-native';
        bottomAudio.preload = 'auto';
        document.body.appendChild(bottomAudio);
    }

    function formatTimeSec(sec) {
        if (isNaN(sec) || sec < 0) return '00:00';
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }

    window.loadBottomPlayer = function(info, autoPlay = true) {
        const dock = document.getElementById('bottom-player-dock');
        if (dock) dock.style.display = 'flex';

        const titleEl = document.getElementById('bpd-title');
        const subEl = document.getElementById('bpd-sub');
        const artEl = document.getElementById('bpd-art');
        const dlBtn = document.getElementById('bpd-download-btn');
        const totalTimeEl = document.getElementById('bpd-time-total');

        if (titleEl) titleEl.textContent = (info.voice_name ? info.voice_name + ': ' : '') + (info.text || 'OmniVoice Speech');
        if (subEl) subEl.textContent = (info.time_str ? info.time_str + ' · ' : '') + (info.duration ? info.duration + 's' : '');
        if (artEl) {
            artEl.innerHTML = `<span style="font-size:22px;">${info.avatar || '🎙️'}</span>`;
            if (info.grad) artEl.style.background = info.grad;
        }
        if (dlBtn && info.file_url) {
            dlBtn.href = info.file_url;
            dlBtn.download = `OmniVoice_${info.voice_name || 'speech'}_${info.duration || ''}s.wav`;
        }

        if (info.file_url && bottomAudio.src !== info.file_url) {
            bottomAudio.src = info.file_url;
            bottomAudio.load();
        }

        if (info.duration && totalTimeEl) {
            totalTimeEl.textContent = formatTimeSec(info.duration);
        }

        if (autoPlay) {
            bottomAudio.play().then(() => {
                const icon = document.getElementById('bpd-play-ico');
                if (icon) icon.textContent = '⏸';
            }).catch(e => {
                console.log('Autoplay prevented:', e);
            });
        }
    };

    window.omniPlayerTogglePlay = function() {
        if (!bottomAudio.src) return;
        const icon = document.getElementById('bpd-play-ico');
        if (bottomAudio.paused) {
            bottomAudio.play();
            if (icon) icon.textContent = '⏸';
        } else {
            bottomAudio.pause();
            if (icon) icon.textContent = '▶';
        }
    };

    window.omniPlayerRewind = function(sec = 10) {
        if (!bottomAudio.src) return;
        bottomAudio.currentTime = Math.max(0, bottomAudio.currentTime - sec);
    };

    window.omniPlayerForward = function(sec = 10) {
        if (!bottomAudio.src) return;
        bottomAudio.currentTime = Math.min(bottomAudio.duration || 999999, bottomAudio.currentTime + sec);
    };

    window.omniPlayerSeek = function(e) {
        if (!bottomAudio.src || !bottomAudio.duration) return;
        const track = document.getElementById('bpd-progress-track');
        if (!track) return;
        const rect = track.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const ratio = Math.max(0, Math.min(1, clickX / rect.width));
        bottomAudio.currentTime = ratio * bottomAudio.duration;
    };

    bottomAudio.addEventListener('timeupdate', () => {
        const curTimeEl = document.getElementById('bpd-time-current');
        const fillEl = document.getElementById('bpd-progress-fill');
        const handleEl = document.getElementById('bpd-progress-handle');
        if (curTimeEl) curTimeEl.textContent = formatTimeSec(bottomAudio.currentTime);
        if (bottomAudio.duration && !isNaN(bottomAudio.duration)) {
            const pct = (bottomAudio.currentTime / bottomAudio.duration) * 100;
            if (fillEl) fillEl.style.width = pct + '%';
            if (handleEl) handleEl.style.left = pct + '%';
        }
    });

    bottomAudio.addEventListener('loadedmetadata', () => {
        const totalTimeEl = document.getElementById('bpd-time-total');
        if (totalTimeEl && bottomAudio.duration && !isNaN(bottomAudio.duration)) {
            totalTimeEl.textContent = formatTimeSec(bottomAudio.duration);
        }
    });

    bottomAudio.addEventListener('ended', () => {
        const icon = document.getElementById('bpd-play-ico');
        if (icon) icon.textContent = '▶';
        const fillEl = document.getElementById('bpd-progress-fill');
        const handleEl = document.getElementById('bpd-progress-handle');
        if (fillEl) fillEl.style.width = '0%';
        if (handleEl) handleEl.style.left = '0%';
    });

    // History card item play
    window.playHistoryItem = function(fileUrl, voiceName, textSnippet, avatar, dur, timeStr) {
        window.loadBottomPlayer({
            file_url: fileUrl,
            voice_name: voiceName,
            text: textSnippet,
            avatar: avatar,
            duration: dur,
            time_str: timeStr
        }, true);
    };

    window.restoreTextFromHistorySnippet = function(text) {
        const ed = document.querySelector('.editor textarea');
        if (ed) {
            ed.value = text;
            ed.dispatchEvent(new Event('input', { bubbles: true }));
            ed.dispatchEvent(new Event('change', { bubbles: true }));
        }
    };

    window.deleteHistorySingle = function(fid) {
        const bridge = document.getElementById('hist-delete-bridge');
        if (bridge) {
            const input = bridge.querySelector('input, textarea');
            if (input) {
                input.value = fid;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
    };

    // 5. Observer for Generation Complete (Image 3)
    let lastProcessedGenInfo = '';
    const genObserver = new MutationObserver(() => {
        const el = document.querySelector('#latest-generated-info textarea, #latest-generated-info input');
        if (el && el.value && el.value !== lastProcessedGenInfo) {
            lastProcessedGenInfo = el.value;
            try {
                const info = JSON.parse(el.value);
                if (info && info.file_url) {
                    window.loadBottomPlayer(info, true);
                    setTimeout(() => {
                        window.switchSettingsTab('history');
                    }, 80);
                }
            } catch(e) {
                console.error('Error handling generated info:', e);
            }
        }
    });
    genObserver.observe(document.body, { childList: true, subtree: true });

    // Handle initial tab / page URL parameters
    const targetPage = urlObj.searchParams.get('page');
    if (targetPage === 'creator') {
        window.switchOmniVoicePage('creator');
    }
}
"""

# ---------------------------------------------------------------------------
# Complete CSS Theme (Light & Dark with High Spec)
# ---------------------------------------------------------------------------
OMNIVOICE_CSS = """
html:not(.dark), :root {
    --body-background-fill: #ffffff;
    --background-fill-primary: #ffffff;
    --background-fill-secondary: #f8fafc;
    --block-background-fill: transparent;
    --block-border-width: 0px;
    --block-border-color: transparent;
    --block-shadow: none;
    --block-label-background-fill: transparent;
    --block-label-text-color: #0f172a;
    --block-title-text-color: #0f172a;
    --body-text-color: #0f172a;
    --body-text-color-subdued: #64748b;
    --border-color-primary: #e5e7eb;
    --input-background-fill: #ffffff;
    --input-border-color: #e5e7eb;
    --input-border-width: 1px;
    --input-shadow: none;
    --input-radius: 10px;
    --input-placeholder-color: #9ca3af;
    --color-accent: #111111;
    --slider-color: #111111;
    --button-primary-background-fill: #111111;
    --button-primary-text-color: #ffffff;
    --checkbox-background-color-selected: #111111;
    --checkbox-border-color-selected: #111111;

    /* Semantic Theme Tokens (Light Mode) */
    --bg-page: #ffffff;
    --bg-sidebar: #fafafa;
    --bg-settings: #fafafa;
    --bg-card: #ffffff;
    --bg-card-subtle: #f8fafc;
    --bg-card-hover: #f1f5f9;
    --border-col: #ececec;
    --border-card: #e5e7eb;
    --border-card-hover: #cbd5e1;
    --border-focus: #0f172a;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --btn-primary-bg: #0f172a;
    --btn-primary-fg: #ffffff;
    --btn-primary-hover: #1e293b;
    --btn-secondary-bg: #f1f5f9;
    --btn-secondary-fg: #334155;
    --btn-secondary-hover: #e2e8f0;
    --chip-bg: #f8fafc;
    --chip-border: #e2e8f0;
    --chip-hover-bg: #f1f5f9;
    --card-shadow: 0 1px 3px rgba(0,0,0,0.05);
    --hero-promo-grad: linear-gradient(135deg, #ff5e3a 0%, #ff9500 100%);
}

html.dark {
    --body-background-fill: #09090b;
    --background-fill-primary: #09090b;
    --background-fill-secondary: #121318;
    --block-background-fill: transparent;
    --block-border-width: 0px;
    --block-border-color: transparent;
    --block-shadow: none;
    --block-label-background-fill: transparent;
    --block-label-text-color: #f8fafc;
    --block-title-text-color: #f8fafc;
    --body-text-color: #f8fafc;
    --body-text-color-subdued: #94a3b8;
    --border-color-primary: #222736;
    --input-background-fill: #11131a;
    --input-border-color: #272d3d;
    --input-border-width: 1px;
    --input-shadow: none;
    --input-radius: 10px;
    --input-placeholder-color: #64748b;
    --color-accent: #f8fafc;
    --slider-color: #f8fafc;
    --button-primary-background-fill: #f8fafc;
    --button-primary-text-color: #09090b;
    --checkbox-background-color-selected: #f8fafc;
    --checkbox-border-color-selected: #f8fafc;

    /* Semantic Theme Tokens (Dark Mode) */
    --bg-page: #09090b;
    --bg-sidebar: #0c0d11;
    --bg-settings: #0c0d11;
    --bg-card: #141721;
    --bg-card-subtle: #181b26;
    --bg-card-hover: #1f2433;
    --border-col: #1c1f28;
    --border-card: #252b3b;
    --border-card-hover: #384157;
    --border-focus: #f8fafc;
    --text-primary: #f8fafc;
    --text-secondary: #cbd5e1;
    --text-muted: #64748b;
    --btn-primary-bg: #f8fafc;
    --btn-primary-fg: #09090b;
    --btn-primary-hover: #e2e8f0;
    --btn-secondary-bg: #1c202d;
    --btn-secondary-fg: #e2e8f0;
    --btn-secondary-hover: #262c3e;
    --chip-bg: #131620;
    --chip-border: #252b3b;
    --chip-hover-bg: #1d2232;
    --card-shadow: 0 4px 14px rgba(0,0,0,0.35);
    --hero-promo-grad: linear-gradient(135deg, #ea580c 0%, #c2410c 100%);
}

/* Reset / Global */
html, body, .gradio-container {
    background-color: var(--bg-page) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
}
gradio-app {
    background-color: var(--bg-page) !important;
}
.contain {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
}

/* Base Shell */
.shell {
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    min-height: 100vh !important;
    height: 100vh !important;
    gap: 0 !important;
    align-items: stretch !important;
    overflow: hidden !important;
}

/* Left Sidebar */
.sidebar-col {
    width: 240px !important;
    min-width: 240px !important;
    max-width: 240px !important;
    flex: 0 0 240px !important;
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-col) !important;
    padding: 20px 14px !important;
    display: flex !important;
    flex-direction: column !important;
    flex-shrink: 0 !important;
    height: 100vh !important;
    box-sizing: border-box !important;
    position: sticky !important;
    top: 0 !important;
}
.brand {
    font-size: 19px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text-primary);
    padding: 6px 12px 18px;
    display: flex;
    align-items: center;
    gap: 9px;
}
.brand .bars {
    display: inline-flex;
    gap: 2.5px;
    align-items: flex-end;
    height: 15px;
}
.brand .bars i {
    width: 3.5px;
    background: var(--text-primary);
    border-radius: 2px;
}
.brand .bars i:nth-child(1) { height: 9px; }
.brand .bars i:nth-child(2) { height: 15px; }

.nav-title {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-weight: 700;
    padding: 12px 12px 6px;
}
.nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 10px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
    user-select: none;
    margin-bottom: 2px;
}
.nav-item:hover {
    background: var(--btn-secondary-hover);
    color: var(--text-primary);
}
.nav-item.active {
    background: var(--btn-primary-bg) !important;
    color: var(--btn-primary-fg) !important;
}
.nav-item .ico {
    font-size: 15px;
}
.workspace {
    margin-top: auto;
    padding: 12px;
    border-top: 1px solid var(--border-col);
    display: flex;
    align-items: center;
    gap: 10px;
}
.workspace .dot {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    background: var(--btn-secondary-bg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
}
.workspace .t {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
}
.workspace .s {
    font-size: 10.5px;
    color: var(--text-muted);
}

/* Page Views Container */
.page-view {
    display: none !important;
    flex: 1 1 0% !important;
    min-width: 0 !important;
    width: auto !important;
    max-width: none !important;
    box-sizing: border-box !important;
}
.page-view.active {
    display: flex !important;
}
.page-tts {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}

/* Center Column (TTS) */
.center-col {
    flex: 1 1 0% !important;
    min-width: 0 !important;
    background: var(--bg-page) !important;
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    height: 100vh !important;
    overflow-y: auto !important;
    padding: 0 !important;
    box-sizing: border-box !important;
}
.center-col > * {
    flex-shrink: 0 !important;
    width: 100% !important;
}
.topbar {
    height: 56px;
    border-bottom: 1px solid var(--border-col);
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-page);
    position: sticky;
    top: 0;
    z-index: 10;
}
.topbar .left {
    font-size: 14.5px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
}
.topbar .right {
    display: flex;
    align-items: center;
    gap: 12px;
}
.engine-badge {
    background: rgba(34, 197, 94, 0.12);
    color: #16a34a;
    font-size: 11.5px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
}
.theme-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--btn-secondary-bg);
    border: 1px solid var(--border-card);
    color: var(--text-primary);
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
}
.theme-toggle-btn:hover {
    background: var(--btn-secondary-hover);
}
.avatar-v {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--text-primary);
    color: var(--bg-page);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 700;
}
.work {
    max-width: 820px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 24px 32px 100px !important;
    box-sizing: border-box !important;
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
}
.work > * {
    flex-shrink: 0 !important;
    width: 100% !important;
}

/* Voice chip in editor */
.voice-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px 5px 6px;
    border-radius: 999px;
    background: var(--btn-secondary-bg);
    border: 1px solid var(--border-card);
    font-size: 12.5px;
    margin-bottom: 14px;
}
.voice-chip .av {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: #fff;
}
.voice-chip .nm {
    font-weight: 700;
    color: var(--text-primary);
}
.voice-chip .tg {
    color: var(--text-secondary);
    font-size: 11.5px;
}

/* Editor */
.editor textarea {
    font-size: 16px !important;
    line-height: 1.6 !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 14px !important;
    padding: 18px 20px !important;
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    box-shadow: var(--card-shadow) !important;
}
.editor textarea:focus {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 1px var(--border-focus) !important;
}

/* Chips & Tones */
.tone-title, .hint {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-secondary);
    margin: 16px 0 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.chips {
    gap: 8px !important;
    flex-wrap: wrap !important;
}
.chip {
    background: var(--chip-bg) !important;
    border: 1px solid var(--chip-border) !important;
    color: var(--text-secondary) !important;
    border-radius: 999px !important;
    padding: 5px 12px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    cursor: pointer !important;
}
.chip:hover {
    background: var(--chip-hover-bg) !important;
    color: var(--text-primary) !important;
}
.tone-badge {
    font-size: 11.5px !important;
    color: #2563eb !important;
    margin-top: 4px !important;
}

/* Action row */
.actions {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    margin-top: 20px !important;
    padding-top: 14px !important;
    border-top: 1px solid var(--border-col) !important;
}
.gen-btn {
    background: var(--btn-primary-bg) !important;
    color: var(--btn-primary-fg) !important;
    border-radius: 999px !important;
    padding: 10px 24px !important;
    font-size: 13.5px !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(15,23,42,0.18) !important;
}
.gen-btn:hover {
    background: var(--btn-primary-hover) !important;
    transform: translateY(-1px) !important;
}
.status {
    font-size: 12.5px !important;
    font-weight: 500 !important;
    color: var(--text-muted) !important;
}

/* Right Settings / History Column */
.settings-col {
    width: 360px !important;
    min-width: 360px !important;
    max-width: 360px !important;
    flex: 0 0 360px !important;
    background: var(--bg-settings) !important;
    border-left: 1px solid var(--border-col) !important;
    padding: 20px 20px 100px !important;
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    overflow-y: auto !important;
    box-sizing: border-box !important;
}
.settings-col [data-testid="block-info"] {
    color: var(--text-primary) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* Tabs in right panel */
.tabs, .tab-wrapper, .tab-container { background: transparent !important; }
button[role="tab"] {
    font-weight: 600 !important;
    font-size: 14px !important;
    color: var(--text-muted) !important;
}
button[role="tab"][aria-selected="true"] {
    color: var(--text-primary) !important;
    border-color: var(--text-primary) !important;
}

/* Promo Banner */
.promo {
    background: var(--hero-promo-grad) !important;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 18px;
    box-shadow: 0 6px 18px rgba(255,120,50,.24);
}
.promo .a { font-size: 13.5px; font-weight: 700; color: #fff; }
.promo .b { font-size: 11.5px; color: #fff; opacity: .95; margin-top: 3px; }

.model-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 12px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}
.model-card .l { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: var(--text-primary) !important; }
.model-card .tag { font-size: 10.5px; font-weight: 700; border: 1px solid var(--border-card); border-radius: 6px; padding: 1px 6px; }
.model-card .r { font-size: 11.5px; color: #2563eb; font-weight: 500; }
.field-label { font-size: 13px; font-weight: 600; color: var(--text-primary) !important; margin: 2px 0 6px; }

/* =========================================================================
   REQUIREMENT 1: VOICE PREVIEW CARD (Image 1) & MODAL (Image 2)
   ========================================================================= */
.voice-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    margin-top: 4px;
}
.vch-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
}
.vch-reset-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 4px;
    border-radius: 6px;
    transition: color 0.15s ease;
}
.vch-reset-btn:hover {
    color: var(--text-primary);
}
.voice-preview-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    transition: all 0.15s ease;
}
.voice-preview-card:hover {
    border-color: var(--border-card-hover);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.vpc-thumb {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    box-shadow: 0 3px 10px rgba(99,102,241,0.25);
    transition: transform 0.15s ease;
}
.vpc-thumb:hover {
    transform: scale(1.06);
}
.vpc-play-ico {
    color: #ffffff;
    font-size: 15px;
    margin-left: 2px;
}
.vpc-details {
    flex: 1;
    min-width: 0;
}
.vpc-title-row {
    display: flex;
    align-items: center;
    gap: 6px;
}
.vpc-name {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.vpc-badge-info {
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
}
.vpc-sub {
    font-size: 11.5px;
    color: var(--text-secondary);
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.vpc-swap-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    color: var(--text-primary);
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.2s ease;
}
.vpc-swap-btn:hover {
    background: var(--btn-secondary-hover);
    border-color: var(--border-card-hover);
    transform: rotate(180deg);
}

/* Modal Overlay (Image 2) */
.voice-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
}
.voice-modal-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 20px;
    width: 100%;
    max-width: 860px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 60px rgba(0,0,0,0.35);
    overflow: hidden;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modalPop {
    from { opacity: 0; transform: scale(0.96) translateY(8px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}
.vm-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px 12px;
}
.vm-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
}
.vm-close-btn {
    background: transparent;
    border: none;
    font-size: 18px;
    color: var(--text-muted);
    cursor: pointer;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.15s ease;
}
.vm-close-btn:hover {
    background: var(--btn-secondary-hover);
    color: var(--text-primary);
}
.vm-tabs {
    display: flex;
    gap: 24px;
    padding: 0 24px;
    border-bottom: 1px solid var(--border-col);
}
.vm-tab {
    background: transparent;
    border: none;
    padding: 10px 0 12px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-muted);
    cursor: pointer;
    position: relative;
    transition: color 0.15s ease;
}
.vm-tab:hover {
    color: var(--text-primary);
}
.vm-tab.active {
    color: var(--text-primary);
}
.vm-tab.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--text-primary);
    border-radius: 2px;
}
.vm-search-row {
    display: flex;
    gap: 12px;
    padding: 16px 24px 10px;
}
.vm-search-input-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 0 14px;
    height: 42px;
}
.vm-search-input-wrap input {
    border: none;
    background: transparent;
    outline: none;
    font-size: 13.5px;
    color: var(--text-primary);
    width: 100%;
}
.vm-search-input-wrap input::placeholder {
    color: var(--text-muted);
}
.vm-filters-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    cursor: pointer;
}
.vm-chips-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 24px 14px;
    overflow-x: auto;
}
.vm-chips-label {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 600;
}
.vm-chip {
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
}
.vm-chip:hover, .vm-chip.active {
    background: var(--text-primary);
    color: var(--bg-page);
    border-color: var(--text-primary);
}
.vm-list-container {
    flex: 1;
    overflow-y: auto;
    padding: 8px 24px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.vm-voice-row {
    display: flex;
    align-items: center;
    gap: 14px;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    padding: 12px 16px;
    transition: all 0.15s ease;
}
.vm-voice-row:hover {
    border-color: var(--border-card-hover);
    box-shadow: 0 4px 14px rgba(0,0,0,0.05);
}
.vm-card-art {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    position: relative;
    overflow: hidden;
}
.vm-card-art-play {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgba(0,0,0,0.45);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    padding-left: 2px;
    backdrop-filter: blur(2px);
    transition: transform 0.15s ease;
}
.vm-card-art:hover .vm-card-art-play {
    transform: scale(1.15);
    background: rgba(0,0,0,0.7);
}
.vm-card-main {
    flex: 1;
    min-width: 0;
}
.vm-card-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.vm-card-desc {
    font-size: 12px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
}
.vm-card-badges {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}
.vm-badge {
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
}
.vm-use-btn {
    background: var(--btn-primary-bg);
    color: var(--btn-primary-fg);
    border: none;
    border-radius: 999px;
    padding: 8px 16px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
    transition: all 0.15s ease;
}
.vm-use-btn:hover {
    background: var(--btn-primary-hover);
    transform: scale(1.02);
}
.vm-icon-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 16px;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.vm-icon-btn:hover {
    color: var(--text-primary);
}

/* =========================================================================
   REQUIREMENT 2: PERSISTENT BOTTOM PLAYER DOCK & HISTORY (Image 3)
   ========================================================================= */
.bottom-player-dock {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 78px;
    background: var(--bg-card);
    border-top: 1px solid var(--border-col);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.08);
    padding: 0 28px;
    box-sizing: border-box;
}
.bpd-inner {
    width: 100%;
    max-width: 1400px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
}
.bpd-left {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 280px;
    flex-shrink: 0;
    overflow: hidden;
}
.bpd-art {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 3px 10px rgba(99,102,241,0.2);
}
.bpd-text-wrap {
    min-width: 0;
    overflow: hidden;
}
.bpd-title {
    font-size: 13.5px;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.bpd-sub {
    font-size: 11.5px;
    color: var(--text-secondary);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.bpd-center {
    flex: 1;
    max-width: 680px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}
.bpd-btns {
    display: flex;
    align-items: center;
    gap: 16px;
}
.bpd-btn {
    background: transparent;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.1s ease, color 0.15s ease;
}
.bpd-skip {
    font-size: 16px;
    color: var(--text-secondary);
    gap: 2px;
}
.bpd-skip-num {
    font-size: 10px;
    font-weight: 700;
}
.bpd-skip:hover {
    color: var(--text-primary);
    transform: scale(1.1);
}
.bpd-play-btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: var(--text-primary);
    color: var(--bg-page);
    font-size: 14px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.18);
    padding-left: 2px;
}
.bpd-play-btn:hover {
    transform: scale(1.08);
}
.bpd-scrub-row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
}
.bpd-time {
    font-size: 11.5px;
    font-weight: 500;
    color: var(--text-muted);
    min-width: 36px;
    font-variant-numeric: tabular-nums;
}
.bpd-progress-track {
    flex: 1;
    height: 5px;
    background: var(--border-card);
    border-radius: 999px;
    position: relative;
    cursor: pointer;
    transition: height 0.15s ease;
}
.bpd-progress-track:hover {
    height: 7px;
}
.bpd-progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    width: 0%;
    background: var(--text-primary);
    border-radius: 999px;
}
.bpd-progress-handle {
    position: absolute;
    top: 50%;
    left: 0%;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: var(--text-primary);
    transform: translate(-50%, -50%);
    opacity: 0;
    transition: opacity 0.15s ease;
}
.bpd-progress-track:hover .bpd-progress-handle {
    opacity: 1;
}
.bpd-right {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 280px;
    justify-content: flex-end;
}
.bpd-icon-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 16px;
    cursor: pointer;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
    text-decoration: none;
}
.bpd-icon-btn:hover, .bpd-icon-btn.active {
    background: var(--btn-secondary-hover);
    color: var(--text-primary);
}
.bpd-dl-btn {
    border: 1px solid var(--border-card);
}

/* History Cards (Image 3) */
.hist-actions-bar {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    margin-bottom: 10px !important;
    padding-bottom: 8px !important;
    border-bottom: 1px solid var(--border-col) !important;
}
.btn-clear-hist, .btn-refresh-hist {
    font-size: 11.5px !important;
    border-radius: 8px !important;
    padding: 3px 8px !important;
    cursor: pointer !important;
}
.hist-empty {
    text-align: center;
    padding: 36px 16px;
    background: var(--bg-card-subtle);
    border-radius: 12px;
    border: 1px dashed var(--border-card);
    margin-top: 10px;
}
.hist-empty .ico { font-size: 28px; margin-bottom: 6px; }
.hist-empty .tit { font-size: 13.5px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
.hist-empty .desc { font-size: 12px; color: var(--text-muted); line-height: 1.45; }

.hist-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
    max-height: 520px;
    overflow-y: auto;
    padding-right: 2px;
}
.hist-card-row {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.15s ease;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.hist-card-row:hover {
    border-color: var(--border-card-hover);
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.hist-card-play-btn {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    color: var(--text-primary);
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s ease;
    padding-left: 2px;
}
.hist-card-play-btn:hover {
    background: var(--text-primary);
    color: var(--bg-page);
    border-color: var(--text-primary);
    transform: scale(1.05);
}
.hist-card-content {
    flex: 1;
    min-width: 0;
}
.hist-card-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.4;
}
.hist-card-sub {
    font-size: 11.5px;
    color: var(--text-secondary);
    margin-top: 2px;
    display: flex;
    align-items: center;
    gap: 4px;
}
.hist-card-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}
.hist-act-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 14px;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    transition: color 0.15s ease;
}
.hist-act-btn:hover {
    color: var(--text-primary);
}
.hist-badge-pill {
    font-size: 10px;
    font-weight: 700;
    background: rgba(139, 92, 246, 0.12);
    color: #8b5cf6;
    padding: 2px 7px;
    border-radius: 999px;
}

/* =========================================================================
   REQUIREMENT 3: DEDICATED VOICE CREATOR PAGE (Image 4)
   ========================================================================= */
.page-creator {
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    height: 100vh !important;
    overflow-y: auto !important;
    padding: 32px 48px 120px !important;
    background: var(--bg-page) !important;
    box-sizing: border-box !important;
}
.page-creator > * {
    flex-shrink: 0 !important;
    width: 100% !important;
    max-width: 1080px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
.creator-page-container {
    max-width: 1080px;
    margin: 0 auto;
    width: 100%;
}
.creator-topbar {
    margin-bottom: 24px;
}
.creator-main-title {
    font-size: 28px;
    font-weight: 800;
    color: var(--text-primary);
    margin: 0 0 6px 0;
    letter-spacing: -0.02em;
}
.creator-main-desc {
    font-size: 14.5px;
    color: var(--text-secondary);
    margin: 0;
}
.creator-section-heading {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 22px 0 12px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.csh-sub {
    font-size: 13px;
    font-weight: 400;
    color: var(--text-muted);
}
.creator-import-row {
    display: flex !important;
    gap: 16px !important;
    align-items: stretch !important;
    margin-bottom: 20px !important;
}
.import-card-col {
    flex: 1 !important;
    background: var(--bg-card) !important;
    border-radius: 18px !important;
    padding: 24px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    box-sizing: border-box !important;
    transition: all 0.15s ease !important;
}
.upload-card-col {
    border: 2px dashed #a78bfa !important;
    background: var(--bg-card-subtle) !important;
}
.upload-card-col:hover {
    border-color: #8b5cf6 !important;
}
.record-card-col {
    border: 1px solid var(--border-card) !important;
}
.record-card-col:hover {
    border-color: var(--border-card-hover) !important;
}
.import-divider-col {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 6px;
    color: var(--text-muted);
    font-size: 13.5px;
    font-weight: 500;
}
.import-card-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 12px;
}
.ich-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: rgba(139, 92, 246, 0.12);
    color: #8b5cf6;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin-bottom: 10px;
}
.ich-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 3px;
}
.ich-sub {
    font-size: 12.5px;
    color: var(--text-muted);
}
.import-audio-box {
    width: 100% !important;
}
.import-audio-box .wrap, .import-audio-box .upload-container {
    border: none !important;
    background: transparent !important;
}
.creator-guideline-banner {
    background: var(--bg-card-subtle);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    padding: 16px 20px;
    display: flex;
    gap: 14px;
    margin-bottom: 20px;
    line-height: 1.5;
}
.cgb-icon {
    font-size: 20px;
    color: #6366f1;
    flex-shrink: 0;
    margin-top: 2px;
}
.cgb-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.cgb-desc {
    font-size: 12px;
    color: var(--text-secondary);
}
.creator-adv-toggles {
    display: flex !important;
    gap: 20px !important;
    margin-bottom: 16px !important;
}
.creator-asr-bar {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    margin-bottom: 10px !important;
}
.btn-asr {
    background: var(--btn-secondary-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    padding: 6px 14px !important;
}
.creator-ref-textbox textarea {
    border: 1px solid var(--border-card) !important;
    border-radius: 12px !important;
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    font-size: 13.5px !important;
}
.creator-meta-row {
    display: flex !important;
    gap: 12px !important;
    margin-top: 10px !important;
}
.btn-save-voice-full {
    background: var(--btn-primary-bg) !important;
    color: var(--btn-primary-fg) !important;
    border-radius: 999px !important;
    padding: 14px 24px !important;
    font-size: 14px !important;
    font-weight: 700 !important;
    width: 100% !important;
    margin-top: 14px !important;
    box-shadow: 0 4px 16px rgba(15,23,42,0.18) !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}
.btn-save-voice-full:hover {
    background: var(--btn-primary-hover) !important;
    transform: translateY(-1px) !important;
}
.custom-voice-card {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    margin-bottom: 10px !important;
    box-shadow: var(--card-shadow) !important;
}
.cvc-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cvc-info { display: flex; align-items: center; gap: 10px; }
.cvc-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--btn-secondary-bg); display: flex; align-items: center; justify-content: center; font-size: 16px; }
.cvc-name { font-weight: 700; font-size: 14px; color: var(--text-primary); }
.cvc-tag { font-size: 11px; font-weight: 600; background: var(--btn-secondary-bg); color: var(--text-secondary); padding: 3px 10px; border-radius: 999px; }
.cvc-ref { font-size: 12px; color: var(--text-secondary); font-style: italic; margin-bottom: 8px; background: var(--bg-card-subtle); padding: 8px 12px; border-radius: 8px; border-left: 3px solid #6366f1; line-height: 1.4; }
.cvc-actions { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.btn-use-in-tts {
    background: var(--btn-secondary-bg);
    border: 1px solid var(--border-card);
    color: var(--text-primary);
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
}
.btn-use-in-tts:hover {
    background: var(--text-primary);
    color: var(--bg-page);
}

/* Explicit high-specificity dark overrides */
html.dark .sidebar-col {
    background: #0c0d11 !important;
    border-right: 1px solid #1c1f28 !important;
}
html.dark .center-col {
    background: #09090b !important;
}
html.dark .settings-col {
    background: #0c0d11 !important;
    border-left: 1px solid #1c1f28 !important;
}
html.dark .topbar {
    background: #09090b !important;
    border-bottom: 1px solid #1c1f28 !important;
}
html.dark .editor textarea {
    background: #11131a !important;
    border-color: #222736 !important;
    color: #f8fafc !important;
}
html.dark .bottom-player-dock {
    background: #0f1117 !important;
    border-top: 1px solid #1e2230 !important;
    box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.4) !important;
}
html.dark .voice-modal-card {
    background: #12141c !important;
    border-color: #252b3b !important;
}
"""

# ---------------------------------------------------------------------------
# History Management Functions
# ---------------------------------------------------------------------------
def load_history():
    if not os.path.exists(HISTORY_INDEX):
        return []
    try:
        with open(HISTORY_INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [it for it in data if os.path.exists(it.get("file_path", ""))]
    except Exception as e:
        logging.warning(f"Error loading history: {e}")
        return []


def save_history(items):
    # Ghi ra file tạm rồi thay thế để người đọc không bao giờ thấy file dở dang (bản React đọc/ghi đồng thời)
    tmp = f"{HISTORY_INDEX}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORY_INDEX)
    except Exception as e:
        logging.warning(f"Error saving history: {e}")


def add_to_history(waveform, sampling_rate, text, voice_choice, dur, elapsed):
    fid = f"omni_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    fpath = os.path.join(HISTORY_DIR, f"{fid}.wav")
    try:
        sf.write(fpath, waveform, sampling_rate)
    except Exception as e:
        logging.error(f"Failed to write history audio: {e}")
        return load_history()

    all_v = get_all_voices()
    vinfo = all_v.get(voice_choice, {})
    vname = vinfo.get("name", "Custom Voice")
    vav = vinfo.get("avatar", "🎙️")
    vtag = vinfo.get("style_tag", "Custom")

    item = {
        "id": fid,
        "file_path": fpath,
        "voice_choice": voice_choice,
        "voice_name": vname,
        "avatar": vav,
        "style_tag": vtag,
        "text": text,
        "duration": round(float(dur), 1),
        "elapsed": round(float(elapsed), 1),
        "time_str": datetime.now().strftime("%H:%M · %d/%m"),
        "timestamp": time.time(),
    }
    hist = load_history()
    hist.insert(0, item)
    hist = hist[:50]
    save_history(hist)
    return hist


def render_history_html(items):
    if not items:
        return """
        <div class="hist-empty">
            <div class="ico">📜</div>
            <div class="tit">Chưa có lịch sử tạo giọng</div>
            <div class="desc">Các đoạn audio bạn tạo sẽ được lưu tự động tại đây để bạn nghe lại hoặc tải về bất cứ lúc nào.</div>
        </div>
        """
    cards = []
    for it in items:
        fpath = it.get("file_path", "")
        file_url = f"/gradio_api/file={fpath}"
        text_snippet = it.get("text", "").replace('"', '&quot;')
        voice_nm = it.get("voice_name", "Voice")
        av = it.get("avatar", "🎙️")
        dur = it.get("duration", 0)
        time_str = it.get("time_str", "")
        fid = it.get("id", "")
        clean_text = it.get("text", "").replace("'", "\\'").replace('"', '&quot;').replace("\n", " ")
        cards.append(f"""
        <div class="hist-card-row" id="hist-card-{fid}">
            <button type="button" class="hist-card-play-btn" onclick="window.playHistoryItem('{file_url}', '{voice_nm}', '{clean_text}', '{av}', {dur}, '{time_str}')" title="Phát trong Bottom Player">
                <span class="hist-play-ico">▶</span>
            </button>
            <div class="hist-card-content">
                <div class="hist-card-text" title="{text_snippet}">{text_snippet}</div>
                <div class="hist-card-sub">
                    <span class="hist-sub-name">{voice_nm}</span>
                    <span class="hist-sub-dot">·</span>
                    <span class="hist-sub-time">{time_str}</span>
                </div>
            </div>
            <div class="hist-card-actions">
                <button type="button" class="hist-act-btn" onclick="window.deleteHistorySingle('{fid}')" title="Xóa bản ghi">🗑️</button>
                <button type="button" class="hist-act-btn" onclick="window.restoreTextFromHistorySnippet('{clean_text}')" title="Nạp vào khung soạn thảo">📋</button>
                <a href="{file_url}" download="OmniVoice_{voice_nm}_{dur}s.wav" class="hist-act-btn hist-act-dl" title="Tải file WAV">⬇</a>
                <span class="hist-badge-pill">WAV</span>
            </div>
        </div>
        """)
    return f'<div class="hist-list">{"".join(cards)}</div>'


def get_history_choices(items):
    choices = []
    for it in items:
        snippet = it.get("text", "")[:35] + ("..." if len(it.get("text", "")) > 35 else "")
        label = f"{it.get('avatar', '')} {it.get('voice_name', '')} ({it.get('duration', '')}s): {snippet}"
        choices.append((label, it.get("id")))
    return choices


def clear_all_history():
    hist = load_history()
    for it in hist:
        p = it.get("file_path")
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    save_history([])
    return render_history_html([]), gr.update(choices=[], value=None)


def refresh_history():
    hist = load_history()
    choices = get_history_choices(hist)
    val = hist[0]["id"] if hist else None
    return render_history_html(hist), gr.update(choices=choices, value=val)


def delete_single_history(item_id):
    if not item_id:
        return render_history_html(load_history())
    hist = load_history()
    new_hist = []
    for it in hist:
        if it.get("id") == item_id:
            p = it.get("file_path")
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        else:
            new_hist.append(it)
    save_history(new_hist)
    return render_history_html(new_hist)


# ---------------------------------------------------------------------------
# Custom Voice Management
# ---------------------------------------------------------------------------
def load_custom_voices():
    if not os.path.exists(CUSTOM_VOICES_FILE):
        return {}
    try:
        with open(CUSTOM_VOICES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            valid = {}
            for k, v in data.items():
                if v.get("audio") and os.path.exists(v["audio"]):
                    valid[k] = v
            return valid
    except Exception as e:
        logging.warning(f"Error loading custom voices: {e}")
        return {}


def save_custom_voices(voices_dict):
    try:
        with open(CUSTOM_VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(voices_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Error saving custom voices: {e}")


def get_all_voices():
    voices = dict(PRESET_VOICES)
    custom = load_custom_voices()
    voices.update(custom)
    return voices


def get_voice_choices(all_voices):
    return [
        (f'{v["avatar"]} {v["name"]}' + ("" if k.startswith("🎙") else f' · {v.get("style_tag", "").split(",")[0]}'), k)
        for k, v in all_voices.items()
    ]


def render_custom_voices_html():
    voices = load_custom_voices()
    if not voices:
        return """
        <div class="custom-voice-empty" style="text-align:center; padding:32px 14px; background:var(--bg-card-subtle); border-radius:14px; border:1px dashed var(--border-card); color:var(--text-muted); font-size:13px;">
            <div style="font-size:26px; margin-bottom:8px;">🎙️</div>
            <div style="font-weight:700; color:var(--text-primary); margin-bottom:4px;">Chưa có giọng cá nhân nào</div>
            <div style="font-size:12px; color:var(--text-muted);">Tải lên audio mẫu ở trên hoặc thu âm để bắt đầu nhân bản giọng!</div>
        </div>
        """
    cards = []
    for k, v in voices.items():
        fpath = v.get("audio", "")
        file_url = f"/gradio_api/file={fpath}"
        avatar = v.get('avatar', '🎙️')
        name = v.get('name', 'Voice')
        style_tag = v.get('style_tag', 'Custom Voice')
        ref_text = v.get('ref_text', '')
        key_escaped = k.replace("'", "\\'")
        cards.append(f"""
        <div class="custom-voice-card">
            <div class="cvc-top">
                <div class="cvc-info">
                    <div class="cvc-avatar">{avatar}</div>
                    <span class="cvc-name">{name}</span>
                </div>
                <span class="cvc-tag">{style_tag}</span>
            </div>
            {f'<div class="cvc-ref">"{ref_text}"</div>' if ref_text else ''}
            <div class="cvc-actions">
                <audio controls preload="none" src="{file_url}" style="width:100%; height:32px;"></audio>
                <button type="button" class="btn-use-in-tts" onclick="window.selectVoiceAndGoToTTS('{key_escaped}')">🔊 Dùng trong Text to Speech</button>
            </div>
        </div>
        """)
    return f'<div class="custom-voice-list" style="display:flex; flex-direction:column; gap:8px;">{"".join(cards)}</div>'


# ---------------------------------------------------------------------------
# UI Components Renderers
# ---------------------------------------------------------------------------
def render_voice_card_html(choice, all_voices):
    vinfo = all_voices.get(choice, {})
    name = vinfo.get("name", "PEAKTV")
    style_tag = vinfo.get("style_tag", "Documentary, Tech")
    grad = vinfo.get("grad", "linear-gradient(135deg, #6366f1, #8b5cf6)")
    audio_path = vinfo.get("audio") or ""
    audio_url = f"/gradio_api/file={audio_path}" if audio_path else ""

    return f"""
    <div class="voice-card-header">
        <span class="vch-title">Voice</span>
        <button type="button" class="vch-reset-btn" onclick="window.resetVoiceToDefault()" title="Khôi phục giọng mặc định">
            <span class="vch-reset-ico">⟳</span> Reset Value
        </button>
    </div>
    <div class="voice-preview-card" id="voice-preview-card">
        <div class="vpc-thumb" id="vpc-thumb" style="background: {grad};" onclick="window.toggleCurrentVoiceSample(event)" title="Nghe thử giọng mẫu">
            <span class="vpc-play-ico" id="vpc-play-ico">▶</span>
        </div>
        <div class="vpc-details">
            <div class="vpc-title-row">
                <span class="vpc-name" id="vpc-name">{name}</span>
                <span class="vpc-badge-info" title="Xem thông tin giọng">❐</span>
            </div>
            <div class="vpc-sub" id="vpc-sub">{style_tag}</div>
        </div>
        <button type="button" class="vpc-swap-btn" onclick="window.openVoiceModal()" title="Đổi giọng mẫu (Voice Selection)">
            <span class="vpc-swap-ico">⇄</span>
        </button>
    </div>
    """


def render_voice_modal_html(all_voices):
    first_key = list(all_voices.keys())[0]

    # Generate cards for Library & My Voices
    cards_html = []
    for k, v in all_voices.items():
        is_preset = (k in PRESET_VOICES)
        tab = "library" if is_preset else "myvoices"
        name = v.get("name", "Voice")
        style = v.get("style_tag", "")
        desc = v.get("desc", f"Phong cách {style}")
        avatar = v.get("avatar", "🎙️")
        grad = v.get("grad", "linear-gradient(135deg, #6366f1, #8b5cf6)")
        tags = v.get("tags", [style])
        tags_str = " ".join(tags)
        audio_path = v.get("audio") or ""
        audio_url = f"/gradio_api/file={audio_path}" if audio_path else ""
        escaped_key = k.replace("'", "\\'")

        badge_spans = "".join([f'<span class="vm-badge">{t}</span>' for t in tags[:3]])

        cards_html.append(f"""
        <div class="vm-voice-row" data-key="{escaped_key}" data-tab="{tab}" data-name="{name}" data-style="{style}" data-grad="{grad}" data-audio="{audio_url}" data-desc="{desc}" data-tags="{tags_str}">
            <div class="vm-card-art" style="background: {grad};" onclick="window.playVoiceModalSample('{audio_url}', event)">
                <span class="vm-card-art-play">▶</span>
            </div>
            <div class="vm-card-main">
                <div class="vm-card-title">{name} - {style}</div>
                <div class="vm-card-desc">{desc}</div>
            </div>
            <div class="vm-card-badges">
                {badge_spans}
                <button type="button" class="vm-use-btn" onclick="window.selectVoiceFromModal('{escaped_key}')">
                    <span>🔄</span> Use
                </button>
                <button type="button" class="vm-icon-btn" title="Lưu">🔖</button>
                <button type="button" class="vm-icon-btn" title="Tùy chọn">⋮</button>
            </div>
        </div>
        """)

    return f"""
    <div class="voice-modal-overlay" id="voice-modal-overlay" style="display:none;" onclick="if(event.target===this)window.closeVoiceModal()">
        <div class="voice-modal-card" role="dialog" aria-modal="true">
            <div class="vm-header">
                <h2 class="vm-title">Voice Selection</h2>
                <button type="button" class="vm-close-btn" onclick="window.closeVoiceModal()" title="Đóng">✕</button>
            </div>
            <div class="vm-tabs">
                <button type="button" class="vm-tab active" id="vm-tab-library" onclick="window.switchModalTab('library')">Library</button>
                <button type="button" class="vm-tab" id="vm-tab-myvoices" onclick="window.switchModalTab('myvoices')">My Voices</button>
                <button type="button" class="vm-tab" id="vm-tab-collected" onclick="window.switchModalTab('collected')">Collected Voices</button>
            </div>
            <div class="vm-search-row">
                <div class="vm-search-input-wrap">
                    <span class="vm-search-ico">🔍</span>
                    <input type="text" id="vm-search-input" placeholder="Search library voices" oninput="window.filterVoiceModal()" />
                </div>
                <button type="button" class="vm-filters-btn">
                    <span class="vm-filters-ico">🎛</span> Filters
                </button>
            </div>
            <div class="vm-chips-row">
                <span class="vm-chips-label">Try:</span>
                <button type="button" class="vm-chip active" onclick="window.filterVoiceTag('all', this)">All</button>
                <button type="button" class="vm-chip" onclick="window.filterVoiceTag('Tiếng Việt', this)">Tiếng Việt</button>
                <button type="button" class="vm-chip" onclick="window.filterVoiceTag('Documentary', this)">Documentary</button>
                <button type="button" class="vm-chip" onclick="window.filterVoiceTag('Finance', this)">Finance</button>
                <button type="button" class="vm-chip" onclick="window.filterVoiceTag('Narrative', this)">Narrative</button>
                <button type="button" class="vm-chip" onclick="window.filterVoiceTag('Tech', this)">Tech</button>
            </div>
            <div class="vm-list-container" id="vm-list-container">
                {"".join(cards_html)}
            </div>
        </div>
    </div>
    """


def render_bottom_player_html():
    return """
    <div class="bottom-player-dock" id="bottom-player-dock" style="display:none;">
        <div class="bpd-inner">
            <div class="bpd-left">
                <div class="bpd-art" id="bpd-art">
                    <span style="font-size:22px;">🎙️</span>
                </div>
                <div class="bpd-text-wrap">
                    <div class="bpd-title" id="bpd-title">PEAKTV: Hãy tưởng tượng...</div>
                    <div class="bpd-sub" id="bpd-sub">Sẵn sàng phát âm thanh</div>
                </div>
            </div>
            <div class="bpd-center">
                <div class="bpd-btns">
                    <button type="button" class="bpd-btn bpd-skip" onclick="window.omniPlayerRewind(10)" title="Tua lại 10s">
                        <span class="bpd-skip-ico">⟲</span>
                        <span class="bpd-skip-num">10</span>
                    </button>
                    <button type="button" class="bpd-btn bpd-play-btn" id="bpd-play-btn" onclick="window.omniPlayerTogglePlay()" title="Phát / Dừng">
                        <span id="bpd-play-ico">▶</span>
                    </button>
                    <button type="button" class="bpd-btn bpd-skip" onclick="window.omniPlayerForward(10)" title="Tua tới 10s">
                        <span class="bpd-skip-num">10</span>
                        <span class="bpd-skip-ico">⟳</span>
                    </button>
                </div>
                <div class="bpd-scrub-row">
                    <span class="bpd-time" id="bpd-time-current">00:00</span>
                    <div class="bpd-progress-track" id="bpd-progress-track" onclick="window.omniPlayerSeek(event)">
                        <div class="bpd-progress-fill" id="bpd-progress-fill"></div>
                        <div class="bpd-progress-handle" id="bpd-progress-handle"></div>
                    </div>
                    <span class="bpd-time" id="bpd-time-total">00:00</span>
                </div>
            </div>
            <div class="bpd-right">
                <button type="button" class="bpd-icon-btn" title="Thích" onclick="this.classList.toggle('active')">👍</button>
                <button type="button" class="bpd-icon-btn" title="Không thích" onclick="this.classList.toggle('active')">👎</button>
                <a href="#" id="bpd-download-btn" class="bpd-icon-btn bpd-dl-btn" download="omnivoice_speech.wav" title="Tải xuống WAV">
                    <span>⬇</span>
                </a>
            </div>
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# App Builder
# ---------------------------------------------------------------------------
def build_omnivoice_app(model: OmniVoice, checkpoint: str):
    sampling_rate = model.sampling_rate
    all_voices = get_all_voices()

    # Pre-cache voice prompts for presets and custom voices for instantaneous generation
    voice_cache = {}
    for vname, vdata in all_voices.items():
        if vdata.get("audio") and os.path.exists(vdata["audio"]):
            try:
                logging.info(f"Pre-caching prompt for: {vname}")
                voice_cache[vname] = model.create_voice_clone_prompt(
                    ref_audio=vdata["audio"],
                    ref_text=vdata.get("ref_text"),
                )
            except Exception as e:
                logging.warning(f"Could not pre-cache {vname}: {e}")

    def _generate(
        text,
        voice_choice,
        tone_instruct,
        custom_audio,
        custom_ref_text,
        speed,
        guidance_scale,
        num_step,
        language,
        denoise,
        preprocess_prompt,
        postprocess_output,
    ):
        if not text or not text.strip():
            return None, "⚠️ Vui lòng nhập văn bản cần đọc vào khung soạn thảo.", gr.update(), gr.update(), gr.update()

        gen_config = OmniVoiceGenerationConfig(
            num_step=int(num_step or 32),
            guidance_scale=float(guidance_scale or 2.0),
            denoise=bool(denoise),
            preprocess_prompt=bool(preprocess_prompt),
            postprocess_output=bool(postprocess_output),
        )

        lang = language if (language and language != "Auto") else None
        kw = {"text": text.strip(), "language": lang, "generation_config": gen_config}

        if speed is not None and float(speed) != 1.0:
            kw["speed"] = float(speed)

        all_current_voices = get_all_voices()
        if voice_choice in voice_cache:
            kw["voice_clone_prompt"] = voice_cache[voice_choice]
        else:
            chosen = all_current_voices.get(voice_choice, {})
            ref_audio_file = custom_audio or chosen.get("audio")
            ref_text_val = custom_ref_text or chosen.get("ref_text")
            if not ref_audio_file:
                return None, "⚠️ Vui lòng chọn giọng có sẵn hoặc tải file mẫu âm thanh lên.", gr.update(), gr.update(), gr.update()
            try:
                kw["voice_clone_prompt"] = model.create_voice_clone_prompt(
                    ref_audio=ref_audio_file,
                    ref_text=ref_text_val or None,
                )
            except Exception as e:
                return None, f"❌ Lỗi tạo voice prompt: {e}", gr.update(), gr.update(), gr.update()

        if tone_instruct and tone_instruct.strip():
            kw["instruct"] = tone_instruct.strip()
        else:
            instruct_tag = all_current_voices.get(voice_choice, {}).get("instruct")
            if instruct_tag:
                kw["instruct"] = instruct_tag

        try:
            t0 = time.time()
            audio = model.generate(**kw)
            elapsed = time.time() - t0
        except Exception as e:
            return None, f"❌ Lỗi tổng hợp: {type(e).__name__}: {e}", gr.update(), gr.update(), gr.update()

        waveform = (audio[0] * 32767).astype(np.int16)
        dur = len(waveform) / sampling_rate
        hist_items = add_to_history(waveform, sampling_rate, text.strip(), voice_choice, dur, elapsed)
        hist_html = render_history_html(hist_items)
        hist_choices = get_history_choices(hist_items)
        first_id = hist_items[0]["id"] if hist_items else None

        chosen_meta = all_current_voices.get(voice_choice, {})
        latest_info = json.dumps({
            "id": first_id,
            "file_url": f"/gradio_api/file={hist_items[0]['file_path']}" if hist_items else "",
            "text": text.strip()[:65] + ("..." if len(text.strip()) > 65 else ""),
            "voice_name": hist_items[0].get("voice_name", "Voice") if hist_items else "",
            "avatar": hist_items[0].get("avatar", "🎙️") if hist_items else "",
            "duration": round(float(dur), 1),
            "time_str": hist_items[0].get("time_str", "") if hist_items else "",
            "grad": chosen_meta.get("grad", "linear-gradient(135deg,#6366f1,#8b5cf6)"),
        })

        return (
            (sampling_rate, waveform),
            f"✅ Hoàn thành · {dur:.1f}s âm thanh · {elapsed:.1f}s xử lý",
            hist_html,
            gr.update(choices=hist_choices, value=first_id),
            latest_info,
        )

    def _chip_html(choice):
        all_current_voices = get_all_voices()
        info = all_current_voices.get(choice, {})
        return (
            f'<div class="voice-chip">'
            f'<span class="av" style="background:{info.get("grad", "#334155")}">{info.get("avatar", "🎙️")}</span>'
            f'<span class="nm">{info.get("name", "Custom")}</span>'
            f'<span class="tg">· {info.get("style_tag", "")}</span>'
            f"</div>"
        )

    first_voice = list(all_voices.keys())[0]
    initial_history = load_history()

    with gr.Blocks(title="OmniVoice Studio", fill_width=True) as demo:
        with gr.Row(elem_classes="shell"):
            # ================= LEFT SIDEBAR =================
            with gr.Column(elem_classes="sidebar-col"):
                gr.HTML(
                    """
                    <div class="brand"><span class="bars"><i></i><i></i></span><span>OmniVoice</span></div>
                    <div class="nav-title">Studio</div>
                    <div class="nav-item active" id="nav-item-tts" onclick="window.switchOmniVoicePage('tts')"><span class="ico">🔊</span>Text to Speech</div>
                    <div class="nav-item" id="nav-item-creator" onclick="window.switchOmniVoicePage('creator')"><span class="ico">🎤</span>Voice Creator</div>
                    <div class="nav-item" id="nav-item-history" onclick="window.switchOmniVoicePage('history')"><span class="ico">📜</span>History</div>
                    <div class="nav-title">Giao diện</div>
                    <div class="nav-item theme-nav-toggle" onclick="window.toggleOmniVoiceTheme()"><span class="ico theme-nav-ico">🌙</span><span class="theme-nav-txt">Chế độ tối</span></div>
                    <div class="workspace">
                        <div class="dot">⚡</div>
                        <div><div class="t">OmniVoice Engine</div><div class="s">Apple Silicon · MPS GPU</div></div>
                    </div>
                    """
                )

            # ================= PAGE 1: TEXT TO SPEECH (Center + Settings) =================
            with gr.Row(elem_classes="page-view page-tts active", elem_id="page-tts"):
                # Center Column (Editor + Controls)
                with gr.Column(elem_classes="center-col"):
                    gr.HTML(
                        """
                        <div class="topbar">
                            <div class="left"><span>🔊</span>OmniVoice Studio</div>
                            <div class="right">
                                <span class="engine-badge">🟢 Apple Silicon MPS Active</span>
                                <button class="theme-toggle-btn" onclick="window.toggleOmniVoiceTheme()" title="Chuyển chế độ Sáng / Tối">
                                    <span class="theme-btn-ico">🌙</span>
                                    <span class="theme-btn-txt">Dark</span>
                                </button>
                                <span class="avatar-v">V</span>
                            </div>
                        </div>
                        """
                    )
                    with gr.Column(elem_classes="work"):
                        speaker_pill = gr.HTML(_chip_html(first_voice))

                        text_input = gr.Textbox(
                            label="",
                            show_label=False,
                            container=False,
                            placeholder="Type your text with audio tags like [laughs] to turn into expressive speech...",
                            lines=7,
                            elem_classes="editor",
                            value="Chào mừng các bạn đã quay trở lại. Hôm nay, chúng ta sẽ cùng khám phá câu chuyện phía sau sự thành công của một trong những công nghệ bí ẩn nhất thế giới.",
                        )

                        gr.HTML('<div class="tone-title"><span>🎭</span>Phong cách & Cảm xúc đọc:</div>')
                        with gr.Row(elem_classes="chips"):
                            tone_natural = gr.Button("🎙️ Tự nhiên", elem_classes="chip", size="sm")
                            tone_excited = gr.Button("🔥 Hào hứng", elem_classes="chip", size="sm")
                            tone_whisper = gr.Button("🤫 Thì thầm", elem_classes="chip", size="sm")
                            tone_sad = gr.Button("😔 Trầm buồn", elem_classes="chip", size="sm")
                            tone_news = gr.Button("💼 Thời sự", elem_classes="chip", size="sm")
                            tone_robot = gr.Button("🤖 Robot", elem_classes="chip", size="sm")

                        active_tone_state = gr.State(value="")
                        active_tone_badge = gr.Markdown("🔹 *Cảm xúc đang chọn: Tự nhiên (Default)*", elem_classes="tone-badge")

                        gr.HTML('<div class="hint">Đoạn văn mẫu tham khảo:</div>')
                        with gr.Row(elem_classes="chips"):
                            chip1 = gr.Button("🎙️ Dẫn nhập công nghệ", elem_classes="chip", size="sm")
                            chip2 = gr.Button("🚗 Giới thiệu Cybertruck", elem_classes="chip", size="sm")
                            chip3 = gr.Button("📰 Tin tức tài chính", elem_classes="chip", size="sm")
                            chip4 = gr.Button("💡 Triết lý & Kỷ luật", elem_classes="chip", size="sm")

                        with gr.Row(elem_classes="actions"):
                            generate_btn = gr.Button("Generate speech", variant="primary", elem_classes="gen-btn", scale=0)
                            status_text = gr.Markdown("🟢 Sẵn sàng", elem_classes="status")

                        output_audio = gr.Audio(
                            label="Generated Speech",
                            type="numpy",
                            elem_classes="player",
                            interactive=False,
                            visible=False,
                        )

                # Right Settings / History Column
                with gr.Column(elem_classes="settings-col"):
                    with gr.Tabs():
                        with gr.TabItem("Settings"):
                            gr.HTML(
                                """
                                <div class="promo">
                                    <div class="a">⚡ OmniVoice v1.0 Engine</div>
                                    <div class="b">Tăng tốc GPU Apple Silicon (MPS) · Hỗ trợ 600+ ngôn ngữ</div>
                                </div>
                                """
                            )
                            # Voice Preview Card matching Image 1
                            voice_preview_card_html = gr.HTML(
                                value=render_voice_card_html(first_voice, all_voices),
                            )
                            # Hidden dropdown & bridge to preserve Gradio reactive bindings
                            voice_bridge = gr.Textbox(
                                value=first_voice,
                                elem_id="voice-bridge-input",
                                visible=False,
                            )
                            voice_dropdown = gr.Dropdown(
                                label="Voice",
                                choices=get_voice_choices(all_voices),
                                value=first_voice,
                                interactive=True,
                                allow_custom_value=True,
                                visible=False,
                            )
                            preview_audio = gr.Audio(
                                label="Nghe thử giọng mẫu",
                                value=all_voices[first_voice].get("audio"),
                                type="filepath",
                                interactive=False,
                                visible=False,
                            )
                            preview_ref_text = gr.Markdown(
                                f'🗣️ *"{all_voices[first_voice].get("ref_text", "")}"*',
                                elem_classes="preview-ref",
                                visible=False,
                            )

                            gr.HTML(
                                """
                                <div class="field-label">Model</div>
                                <div class="model-card">
                                    <div class="l"><span class="tag">v4</span>OmniVoice Core</div>
                                    <div class="r">Best practices ↗</div>
                                </div>
                                """
                            )

                            speed_slider = gr.Slider(0.5, 1.5, value=1.0, step=0.05, label="Speed", info="1.0 = bình thường · kéo phải để đọc nhanh hơn")
                            cfg_slider = gr.Slider(1.0, 4.0, value=2.0, step=0.1, label="Similarity", info="Độ bám sát giọng mẫu (CFG) · mặc định 2.0")
                            steps_slider = gr.Slider(16, 64, value=32, step=1, label="Quality", info="Inference steps · 32 chuẩn · 40–50 chi tiết hơn")
                            lang_dropdown = gr.Dropdown(label="Language", choices=_ALL_LANGUAGES, value="Auto", interactive=True, info="Auto = tự nhận diện ngôn ngữ")

                            with gr.Accordion("Custom voice (tải mẫu riêng)", open=False):
                                custom_audio_input = gr.Audio(label="Reference Audio (3–10s)", type="filepath")
                                custom_ref_text_input = gr.Textbox(
                                    label="Reference Text (khớp 100% audio)",
                                    lines=2,
                                    placeholder="Gõ chính xác từng từ trong đoạn audio mẫu...",
                                )
                                denoise_chk = gr.Checkbox(label="Denoise", value=True)
                                pre_chk = gr.Checkbox(label="Preprocess Prompt", value=True)
                                post_chk = gr.Checkbox(label="Postprocess Output", value=True)

                        with gr.TabItem("History"):
                            with gr.Row(elem_classes="hist-actions-bar"):
                                gr.Markdown("### 🎙️ Lịch sử")
                                with gr.Row():
                                    refresh_hist_btn = gr.Button("🔄 Làm mới", size="sm", elem_classes="btn-refresh-hist", scale=0)
                                    clear_hist_btn = gr.Button("🗑️ Xóa hết", size="sm", elem_classes="btn-clear-hist", scale=0)

                            history_display = gr.HTML(
                                value=render_history_html(initial_history),
                            )
                            history_restore_dd = gr.Dropdown(
                                choices=get_history_choices(initial_history),
                                value=initial_history[0]["id"] if initial_history else None,
                                visible=False,
                            )
                            hist_delete_bridge = gr.Textbox(elem_id="hist-delete-bridge", visible=False)

            # ================= PAGE 2: VOICE CREATOR (Dedicated Full-Page View Image 4) =================
            with gr.Column(elem_classes="page-view page-creator", elem_id="page-creator"):
                gr.HTML(
                    """
                    <div class="creator-page-container">
                        <div class="creator-topbar">
                            <h1 class="creator-main-title">Voice Cloning</h1>
                            <p class="creator-main-desc">Clone a voice using as little as a 10-second clean voice clip.</p>
                        </div>
                        <div class="creator-section-heading">Import your Voice</div>
                    </div>
                    """
                )
                with gr.Row(elem_classes="creator-import-row"):
                    with gr.Column(elem_classes="import-card-col upload-card-col", scale=1):
                        gr.HTML(
                            """
                            <div class="import-card-header">
                                <div class="ich-icon ich-upload">🎵</div>
                                <div class="ich-title">Add or drop a file</div>
                                <div class="ich-sub">Up to 20MB each</div>
                            </div>
                            """
                        )
                        new_voice_audio_upload = gr.Audio(
                            sources=["upload"],
                            type="filepath",
                            show_label=False,
                            elem_classes="import-audio-box upload-audio-box",
                        )
                    gr.HTML('<div class="import-divider-col"><span>or</span></div>')
                    with gr.Column(elem_classes="import-card-col record-card-col", scale=1):
                        gr.HTML(
                            """
                            <div class="import-card-header">
                                <div class="ich-icon ich-mic">🎙️</div>
                                <div class="ich-title">Record audio</div>
                                <div class="ich-sub">10-60 seconds long</div>
                            </div>
                            """
                        )
                        new_voice_audio_record = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            show_label=False,
                            elem_classes="import-audio-box record-audio-box",
                        )

                gr.HTML(
                    """
                    <div class="creator-guideline-banner">
                        <div class="cgb-icon">ℹ️</div>
                        <div class="cgb-text">
                            <div class="cgb-title">Please upload a clean voice recording in a quiet environment. Reverb, multiple speakers, background noise, etc., will affect the voice cloning quality.</div>
                            <div class="cgb-desc">You can use the noise separation feature to reduce audio noise, but this may also impact the detail of the voice. Therefore, it is recommended to choose the best-quality segment when selecting the material for cloning.</div>
                        </div>
                    </div>
                    """
                )

                gr.HTML('<div class="creator-section-heading">Advanced Settings <span class="csh-sub">(Optional)</span></div>')
                with gr.Row(elem_classes="creator-adv-toggles"):
                    clone_denoise_chk = gr.Checkbox(label="Remove Background Noise ℹ️", value=True)
                    clone_accent_chk = gr.Checkbox(label="Enable Accent Optimization ℹ️", value=True)

                gr.HTML('<div class="creator-section-heading">Text to Preview & Lời thoại mẫu</div>')
                with gr.Row(elem_classes="creator-asr-bar"):
                    auto_asr_btn = gr.Button("⚡ Tự động nhận diện chữ (Whisper ASR)", size="sm", elem_classes="btn-asr")
                    asr_status = gr.Markdown("", elem_classes="asr-status-text")

                new_voice_ref_text = gr.Textbox(
                    label="Nội dung câu nói trong audio (Reference Text)",
                    placeholder="Nhấn nút nhận diện tự động ở trên hoặc tự gõ câu nói trong audio...",
                    lines=2,
                    elem_classes="creator-ref-textbox",
                )

                with gr.Row(elem_classes="creator-meta-row"):
                    new_voice_name = gr.Textbox(label="Tên giọng", placeholder="Ví dụ: PEAKTV, MC Thảo", scale=3)
                    new_voice_avatar = gr.Dropdown(label="Icon", choices=["🎙️", "👑", "🚀", "💼", "🎭", "🎧", "🎬", "✨", "🔥"], value="🎙️", scale=1)
                    new_voice_tag = gr.Textbox(label="Phong cách / Tag", placeholder="Ví dụ: Documentary, Trầm ấm", value="Custom Voice", scale=2)

                save_voice_btn = gr.Button("💾 Clone Voice & Save to Library", elem_classes="btn-save-voice-full", variant="primary")
                save_voice_status = gr.Markdown("", elem_classes="save-status-msg")

                gr.HTML('<div class="creator-section-heading" style="margin-top:28px;">📚 Thư viện giọng đã nhân bản (Cloned Voices)</div>')
                custom_voices_list_html = gr.HTML(value=render_custom_voices_html())

        # ================= VOICE SELECTION MODAL (Image 2) =================
        voice_modal_html = gr.HTML(value=render_voice_modal_html(all_voices))

        # ================= PERSISTENT BOTTOM PLAYER DOCK (Image 3) =================
        bottom_player_html = gr.HTML(value=render_bottom_player_html())

        # Hidden bridge textboxes for reactive events
        latest_generated_info = gr.Textbox(elem_id="latest-generated-info", visible=False)

        # ---------------- Callbacks ----------------
        def _on_voice_change(choice):
            pill = _chip_html(choice)
            all_current_voices = get_all_voices()
            info = all_current_voices.get(choice, {})
            audio_path = info.get("audio")
            ref_txt = info.get("ref_text", "")
            ref_md = f'🗣️ *"{ref_txt}"*' if ref_txt else ""
            card_html = render_voice_card_html(choice, all_current_voices)
            return pill, audio_path, ref_md, card_html, choice

        voice_bridge.change(
            _on_voice_change,
            inputs=[voice_bridge],
            outputs=[speaker_pill, preview_audio, preview_ref_text, voice_preview_card_html, voice_dropdown],
        )

        voice_dropdown.change(
            _on_voice_change,
            inputs=[voice_dropdown],
            outputs=[speaker_pill, preview_audio, preview_ref_text, voice_preview_card_html, voice_dropdown],
        )

        tone_natural.click(lambda: ("", "🔹 *Cảm xúc đang chọn: Tự nhiên (Default)*"), outputs=[active_tone_state, active_tone_badge])
        tone_excited.click(lambda: ("excited, energetic, upbeat", "🔥 *Cảm xúc đang chọn: Hào hứng & Năng lượng cao*"), outputs=[active_tone_state, active_tone_badge])
        tone_whisper.click(lambda: ("whispering, low volume, mysterious", "🤫 *Cảm xúc đang chọn: Thì thầm & Bí ẩn*"), outputs=[active_tone_state, active_tone_badge])
        tone_sad.click(lambda: ("melancholic, soft, emotional, slow", "😔 *Cảm xúc đang chọn: Trầm buồn & Sâu lắng*"), outputs=[active_tone_state, active_tone_badge])
        tone_news.click(lambda: ("formal, news anchor, clear, professional", "💼 *Cảm xúc đang chọn: Thời sự & Nghiêm túc*"), outputs=[active_tone_state, active_tone_badge])
        tone_robot.click(lambda: ("flat tone, robotic, monotone", "🤖 *Cảm xúc đang chọn: Giọng Robot AI*"), outputs=[active_tone_state, active_tone_badge])

        chip1.click(lambda: "Chào mừng các bạn đã quay trở lại. Hôm nay, chúng ta sẽ cùng khám phá câu chuyện phía sau sự thành công của một trong những công nghệ bí ẩn nhất thế giới.", outputs=[text_input])
        chip2.click(lambda: "Mục tiêu của chúng tôi đó là tạo ra một cỗ máy thực dụng hơn bất kỳ chiếc xe bán tải nào, nhưng vẫn sở hữu gia tốc của một siêu xe thể thao.", outputs=[text_input])
        chip3.click(lambda: "Theo báo cáo mới nhất từ các tổ chức tài chính quốc tế, thị trường thanh toán số đang chứng kiến mức tăng trưởng kỷ lục trong quý vừa qua.", outputs=[text_input])
        chip4.click(lambda: "Nhiều người tin rằng thành công đến từ sự may mắn. Nhưng khi nhìn sâu vào cách họ tư duy và kỷ luật bản thân, bạn sẽ nhận ra mọi thành quả đều có lý do của nó.", outputs=[text_input])

        generate_btn.click(
            _generate,
            inputs=[
                text_input, voice_dropdown, active_tone_state, custom_audio_input, custom_ref_text_input,
                speed_slider, cfg_slider, steps_slider, lang_dropdown,
                denoise_chk, pre_chk, post_chk,
            ],
            outputs=[output_audio, status_text, history_display, history_restore_dd, latest_generated_info],
        )

        def _on_auto_transcribe(upload_audio, record_audio):
            audio_file = upload_audio or record_audio
            if not audio_file or not os.path.exists(audio_file):
                return "", "⚠️ Vui lòng tải lên hoặc thu âm file audio trước."
            try:
                t0 = time.time()
                text = model.transcribe(audio_file)
                elapsed = time.time() - t0
                return text.strip(), f"✅ Nhận diện thành công ({elapsed:.1f}s)!"
            except Exception as e:
                return "", f"❌ Lỗi ASR: {e}"

        auto_asr_btn.click(
            _on_auto_transcribe,
            inputs=[new_voice_audio_upload, new_voice_audio_record],
            outputs=[new_voice_ref_text, asr_status],
        )

        def _on_save_voice(upload_audio, record_audio, ref_text, name, avatar, style_tag):
            audio_file = upload_audio or record_audio
            if not audio_file or not os.path.exists(audio_file):
                return gr.update(), render_custom_voices_html(), render_voice_modal_html(get_all_voices()), "⚠️ Vui lòng tải lên hoặc thu âm audio mẫu."
            name = (name or "").strip()
            if not name:
                return gr.update(), render_custom_voices_html(), render_voice_modal_html(get_all_voices()), "⚠️ Vui lòng nhập tên cho giọng nói."

            ref_text = (ref_text or "").strip()
            if not ref_text:
                try:
                    ref_text = model.transcribe(audio_file).strip()
                except Exception as e:
                    return gr.update(), render_custom_voices_html(), render_voice_modal_html(get_all_voices()), f"❌ Không thể nhận diện lời thoại: {e}"

            vid = f"voice_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            saved_path = os.path.join(CUSTOM_VOICES_DIR, f"{vid}.wav")
            import shutil
            shutil.copy2(audio_file, saved_path)

            key_name = f"{avatar or '🎙️'} {name} - {style_tag or 'Custom Voice'}"
            new_voice_entry = {
                "id": vid,
                "name": name,
                "avatar": avatar or "🎙️",
                "style_tag": style_tag or "Custom Voice",
                "audio": saved_path,
                "audio_url": f"/gradio_api/file={saved_path}",
                "ref_text": ref_text,
                "desc": f"Giọng nhân bản tùy chỉnh: {ref_text[:60]}...",
                "tags": ["Tùy chỉnh", style_tag or "Custom"],
                "grad": "linear-gradient(135deg,#ec4899,#8b5cf6)",
                "instruct": "",
            }

            try:
                voice_cache[key_name] = model.create_voice_clone_prompt(
                    ref_audio=saved_path,
                    ref_text=ref_text,
                )
            except Exception as e:
                logging.warning(f"Error caching new voice: {e}")

            custom_voices = load_custom_voices()
            custom_voices[key_name] = new_voice_entry
            save_custom_voices(custom_voices)

            all_v = get_all_voices()
            new_choices = get_voice_choices(all_v)
            modal_html = render_voice_modal_html(all_v)

            return (
                gr.update(choices=new_choices, value=key_name),
                render_custom_voices_html(),
                modal_html,
                f"✅ Đã clone và lưu giọng '{name}' vào Thư viện thành công!",
            )

        save_voice_btn.click(
            _on_save_voice,
            inputs=[new_voice_audio_upload, new_voice_audio_record, new_voice_ref_text, new_voice_name, new_voice_avatar, new_voice_tag],
            outputs=[voice_dropdown, custom_voices_list_html, voice_modal_html, save_voice_status],
        )

        clear_hist_btn.click(
            clear_all_history,
            outputs=[history_display, history_restore_dd],
        )

        refresh_hist_btn.click(
            refresh_history,
            outputs=[history_display, history_restore_dd],
        )

        hist_delete_bridge.change(
            delete_single_history,
            inputs=[hist_delete_bridge],
            outputs=[history_display],
        )

    return demo


def main():
    parser = argparse.ArgumentParser(description="OmniVoice Studio")
    parser.add_argument("--model", default="k2-fsa/OmniVoice", help="Model checkpoint path")
    parser.add_argument("--device", default=None, help="Device to use")
    parser.add_argument("--ip", default="127.0.0.1", help="Server IP")
    parser.add_argument("--port", type=int, default=7860, help="Server port")
    args = parser.parse_args()

    device = args.device or get_best_device()
    checkpoint = args.model

    logging.info(f"Loading OmniVoice from {checkpoint} on {device}...")
    model_dtype = torch.float32 if str(device).startswith("mps") else torch.float16
    model = OmniVoice.from_pretrained(
        checkpoint,
        device_map=device,
        dtype=model_dtype,
        load_asr=True,
        asr_model_name="openai/whisper-large-v3-turbo",
    )
    logging.info("OmniVoice model ready.")

    demo = build_omnivoice_app(model, checkpoint)
    demo.queue().launch(
        server_name=args.ip,
        server_port=args.port,
        show_error=True,
        allowed_paths=[PRESETS_DIR, HISTORY_DIR, CUSTOM_VOICES_DIR],
        theme=gr.themes.Base(),
        css=OMNIVOICE_CSS,
        js=OMNIVOICE_THEME_JS,
    )


if __name__ == "__main__":
    main()
