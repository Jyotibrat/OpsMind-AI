/**
 * frontend/js/auth.js
 * Shared auth module — token management, role checks, logout
 */

const AUTH_KEY = 'opsmind_token';
const USER_KEY = 'opsmind_user';
const API_BASE = window.location.origin;

/** Store token + user info after login */
function saveAuth(data) {
    localStorage.setItem(AUTH_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify({
        role: data.role,
        display_name: data.display_name,
    }));
}

/** Get stored token */
function getToken() {
    return localStorage.getItem(AUTH_KEY);
}

/** Get stored user info */
function getUser() {
    try {
        return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch { return null; }
}

/** Clear auth and redirect to login */
function logout() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = '/index.html';
}

/** Build Authorization header object */
function authHeaders() {
    return { 'Authorization': `Bearer ${getToken()}` };
}

/**
 * Guard: call on every protected page.
 * - If no token → redirect to login
 * - If role doesn't match requiredRole → redirect accordingly
 */
function requireAuth(requiredRole = null) {
    const token = getToken();
    const user = getUser();

    if (!token || !user) {
        window.location.href = '/index.html';
        return null;
    }

    if (requiredRole && user.role !== requiredRole) {
        // Employee trying to access admin page → send to chat
        if (requiredRole === 'admin') {
            window.location.href = '/chat.html';
        } else {
            window.location.href = '/index.html';
        }
        return null;
    }

    return user;
}

/**
 * Populate sidebar user info (call after requireAuth)
 */
function populateSidebarUser() {
    const user = getUser();
    if (!user) return;

    const nameEl = document.getElementById('sidebar-username');
    const roleEl = document.getElementById('sidebar-role');
    const avEl = document.getElementById('sidebar-avatar');

    if (nameEl) nameEl.textContent = user.display_name;
    if (roleEl) {
        roleEl.textContent = user.role === 'admin' ? '⭐ Admin' : '👤 Employee';
        roleEl.className = `role-badge ${user.role}`;
    }
    if (avEl) avEl.textContent = user.display_name.charAt(0).toUpperCase();

    // Show/hide admin-only nav items
    document.querySelectorAll('[data-admin-only]').forEach(el => {
        el.style.display = user.role === 'admin' ? '' : 'none';
    });
}

/** Show toast notification */
function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: '✓', error: '✗', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${escapeHtml(msg)}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3400);
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Wire logout button
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('logout-btn')?.addEventListener('click', logout);
});

window.Auth = { saveAuth, getToken, getUser, logout, authHeaders, requireAuth, populateSidebarUser, showToast, escapeHtml };
