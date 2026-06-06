const API = '';
let userEmail = '';
let isAuthenticated = true;
const sessionUUID = crypto.randomUUID()

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    loadUserData();
    updateDateTime();
    setInterval(updateDateTime, 1000);
    setupFileUploadDragDrop();
});

// ============================================
// USER DATA FUNCTIONS
// ============================================

async function loadUserData() {
    try {
        const res = await fetch('/get-user-data');
        const data = await res.json();
        
        if (data.status === 'success') {
            populateDashboard(data.user);
        } else {
            window.location.href = data.url || '/auth';
        }
    } catch (error) {
        console.error('Error loading user data:', error);
        window.location.href = '/auth';
    }
}

function populateDashboard(user) {
    // Sidebar user info
    const initial = user.first_name.charAt(0).toUpperCase() || 'U';
    document.getElementById('profileInitial').textContent = initial;
    document.getElementById('userName').textContent = `${user.first_name} ${user.last_name}`;
    document.getElementById('userEmail').textContent = user.email;
    document.getElementById('walletBalance').textContent = (user.wallet_balance || 0).toFixed(2);
    
    // Account number section
    const accountNumberDiv = document.getElementById('accountNumberDiv');
    const generateBtn = document.getElementById('generateAccountBtn');
    
    if (user.has_wallet) {
        document.getElementById('accountNumber').textContent = user.account_number || 'Not Set';
        document.getElementById('bankName').textContent = user.bank_name || '';
        generateBtn.classList.add('hidden');
    } else {
        document.getElementById('accountNumber').textContent = 'Not Generated';
        document.getElementById('bankName').textContent = '';
        generateBtn.classList.remove('hidden');
    }
    
    // Settings page
    document.getElementById('settingsName').textContent = `${user.first_name} ${user.last_name}`;
    document.getElementById('settingsEmail').textContent = user.email;
    document.getElementById('settingsPhone').textContent = user.phone_number || '-';
}

// ============================================
// TAB SWITCHING
// ============================================

function switchTab(tabName) {
    // Hide all tabs
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    // Remove active class from nav links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => link.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Add active class to clicked nav link
    if (tabName === 'payments') {
        document.getElementById('navPayments').classList.add('active');
    } else if (tabName === 'history') {
        document.getElementById('navHistory').classList.add('active');
    } else if (tabName === 'settings') {
        document.getElementById('navSettings').classList.add('active');
    }
}

// ============================================
// ACCOUNT NUMBER GENERATION
// ============================================

async function generateAccountNumber() {
    const btn = document.getElementById('generateAccountBtn');
    btn.textContent = 'Processing...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/generate-account-number');
        const data = await res.json();
        
        if (data.status === 'success') {
            alert('✅ Account number generated successfully!');
            loadUserData();
        } else {
            alert('❌ ' + (data.message || 'Failed to generate account number'));
            if (data.url) {
                window.location.href = data.url;
            }
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    } finally {
        btn.textContent = 'Generate Account Number';
        btn.disabled = false;
    }
}

// ============================================
// PAYMENT EXECUTION
// ============================================

async function executePayment() {
    if (!isAuthenticated) {
        alert('❌ Not authenticated. Please login first');
        return;
    }
    
    const command = document.getElementById('command').value;
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    const successTransfers = document.getElementById("successTransfer");
    const failedTransfers = document.getElementById("failedTransfers");
    
    if (!command) {
        alert('Please enter a payment command');
        return;
    }
    
    const btn = event.target;
    btn.textContent = 'Processing...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/send-money', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({command: command, sessionUUID: sessionUUID})
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            successTransfers.innerHTML = data.success_html_table;
            failedTransfers.innerHTML = data.failed_html_table;
            resultsContent.innerHTML = data.ai_msg;
            
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderColor = '#4caf50';
        } else {
            if (data.url) {
                window.location.href = data.url;
            }
            resultsContent.textContent = data.message || 'Payment failed';
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderColor = '#f44336';
        }
    } catch (error) {
        alert("❌ Error: " + error.message);
    } finally {
        btn.textContent = 'Execute Payment';
        btn.disabled = false;
    }
}

// ============================================
// FILE UPLOAD FUNCTIONALITY
// ============================================

function setupFileUploadDragDrop() {
    const fileInput = document.getElementById('paymentFile');
    const fileLabel = document.querySelector('.file-label');
    
    // Drag and drop events
    fileLabel.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileLabel.style.background = '#e8ebff';
        fileLabel.style.borderColor = '#5568d3';
    });
    
    fileLabel.addEventListener('dragleave', () => {
        fileLabel.style.background = '#f8f9ff';
        fileLabel.style.borderColor = '#667eea';
    });
    
    fileLabel.addEventListener('drop', (e) => {
        e.preventDefault();
        fileLabel.style.background = '#f8f9ff';
        fileLabel.style.borderColor = '#667eea';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileName();
        }
    });
    
    // File input change event
    fileInput.addEventListener('change', updateFileName);
}

function updateFileName() {
    const fileInput = document.getElementById('paymentFile');
    const fileName = document.getElementById('fileName');
    
    if (fileInput.files.length > 0) {
        fileName.textContent = fileInput.files[0].name;
    } else {
        fileName.textContent = 'Choose File or Drag & Drop';
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('paymentFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    const btn = event.target;
    btn.textContent = 'Processing...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/upload-file', {
            method: 'POST',
            body: formData
        });
        
        const data = await res.json();
        
        const resultsDiv = document.getElementById('results');
        const resultsContent = document.getElementById('resultsContent');
        const successTransfers = document.getElementById("successTransfer");
        const failedTransfers = document.getElementById("failedTransfers");
        
        if (data.status === 'success') {
            successTransfers.innerHTML = data.success_html_table;
            failedTransfers.innerHTML = data.failed_html_table;
            resultsContent.innerHTML = data.ai_msg;
            
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderColor = '#4caf50';
            
            alert('✅ File processed successfully!');
        } else {
            resultsContent.textContent = data.message || 'File processing failed';
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderColor = '#f44336';
            
            alert('❌ ' + (data.message || 'File processing failed'));
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    } finally {
        btn.textContent = 'Upload and Process File';
        btn.disabled = false;
    }
}

// ============================================
// SIDEBAR TOGGLE (Mobile)
// ============================================

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('open');
}

// Close sidebar when a nav link is clicked on mobile
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            const sidebar = document.querySelector('.sidebar');
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
            }
        });
    });
});

// ============================================
// DATE AND TIME UPDATE
// ============================================

function updateDateTime() {
    const now = new Date();
    
    // Format time (HH:MM:SS)
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    document.getElementById('headerTime').textContent = `${hours}:${minutes}:${seconds}`;
    
    // Format date (MM/DD/YYYY)
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const year = now.getFullYear();
    document.getElementById('headerDate').textContent = `${month}/${day}/${year}`;
}

// ============================================
// LOGOUT FUNCTION
// ============================================

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        // Clear session and redirect
        fetch('/logout', { method: 'POST' })
            .then(() => {
                window.location.href = '/auth';
            })
            .catch(() => {
                window.location.href = '/auth';
            });
    }
}
