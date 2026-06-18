const API = '';
let userEmail = '';
let isAuthenticated = true;

function getCsrfToken(){
    const value = `; ${document.cookie}`;
    const data = value.split("; csrftoken=")
    if(data.length === 2){
        res = data.pop().split(";").shift()
        return res;
    }else{
        return " ";
    }
}

document.addEventListener('DOMContentLoaded', function() {
    loadUserData();
    updateDateTime();
    setInterval(updateDateTime, 1000);
    setupFileUploadDragDrop();
    initializeSidebarState();
});

// ============================================
// INITIALIZE SIDEBAR STATE
// ============================================

function initializeSidebarState() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const overlay = document.getElementById('overlay');
    
    // Ensure sidebar starts CLOSED on mobile
    if (window.innerWidth <= 768) {
        if (sidebar) {
            sidebar.classList.remove('open');
        }
        if (mainContent) {
            mainContent.classList.remove('blur');
        }
        if (overlay) {
            overlay.classList.remove('active');
        }
    }
}

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
        // Fallback for development/demo
        populateDashboard({
            first_name: 'Demo',
            last_name: 'User',
            email: 'demo@remitron.com',
            phone_number: '+234 800 000 0000',
            wallet_balance: 50000,
            has_wallet: true,
            account_number: '1234567890',
            bank_name: 'Access Bank'
        });
    }
}

function populateDashboard(user) {
    // Sidebar user info
    const initial = user.first_name.charAt(0).toUpperCase() || 'U';
    document.getElementById('profileInitial').textContent = initial;
    document.getElementById('userName').textContent = `${user.first_name} ${user.last_name}`;
    document.getElementById('userEmail').textContent = user.email;
    document.getElementById('walletBalance').textContent = (user.wallet_balance || 0).toFixed(2);
    fetchBalance();
    
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
    document.getElementById('lastLogin').textContent = new Date().toLocaleString();
}

// ============================================
// FETCH BALANCE
// ============================================
function fetchBalance(){
    setInterval(async () => {  // ← Add parentheses after async
        try{
            const res = await fetch("/account-balance");
            const data = await res.json();
            
            if(data.status === "success"){  
                const balance = data.balance || 0.00;
                document.getElementById('walletBalance').textContent = balance.toFixed(2);
    ;
            }
        }catch(error){
            console.error("Balance fetch error:", error);  // Use console.error, not alert
        }
    }, 5000);  // 5000ms = 5 seconds ✓
}

// Call it when page loads
//window.addEventListener('load', fetchBalance);

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
    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.classList.add('active');
    }
    
    // Add active class to clicked nav link
    if (tabName === 'payments') {
        document.getElementById('navPayments').classList.add('active');
    } else if (tabName === 'history') {
        document.getElementById('navHistory').classList.add('active');
    } else if (tabName === 'settings') {
        document.getElementById('navSettings').classList.add('active');
    }
    
    // Close sidebar on mobile after clicking nav
    if (window.innerWidth <= 768) {
        closeSidebar();
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

async function executePayment(event) {
    
    if (event) {
        event.preventDefault();
    }
    
    if (!isAuthenticated) {
        alert('❌ Not authenticated. Please login first');
        return;
    }
    
    const command = document.getElementById('command').value;
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    const successTransfers = document.getElementById("successTransfer");
    const failedTransfers = document.getElementById("failedTransfers");
    
    if (!command.trim()) {
        alert('❌ Please enter a payment command');
        return;
    }
    
    const btn = event.target;
    btn.textContent = 'Processing...';
    btn.disabled = true;

    const idempotency_key = `REMUTRON-${Date.now()}-${Math.random().toString(36).substr(2,9)}`
    
        
    try {
        const res = await fetch('/send-money', {
            method: 'POST',
            headers: {'Content-Type': 'application/json',"X-CSRFToken": getCsrfToken()},
            body: JSON.stringify({command: command, idempotency_key: idempotency_key})
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            successTransfers.innerHTML = data.success_html_table || '<p>No successful transfers</p>';
            failedTransfers.innerHTML = data.failed_html_table || '<p>No failed transfers</p>';
            resultsContent.innerHTML = data.ai_msg || 'Payment processed successfully';
            
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderLeftColor = '#4caf50';
        } else {
            if (data.url) {
                window.location.href = data.url;
            }
            resultsContent.textContent = data.message || 'Payment failed';
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderLeftColor = '#f44336';
        }
    } catch (error) {
        resultsContent.textContent = '❌ Error: ' + error.message;
        resultsDiv.classList.remove('hidden');
        resultsDiv.style.borderLeftColor = '#f44336';
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
    
    if (!fileLabel) return;
    
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

async function uploadFile(event) {
    if (event) {
        event.preventDefault();
    }
    
    const fileInput = document.getElementById('paymentFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('❌ Please select a file');
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
            successTransfers.innerHTML = data.success_html_table || '<p>No successful transfers</p>';
            failedTransfers.innerHTML = data.failed_html_table || '<p>No failed transfers</p>';
            resultsContent.innerHTML = data.ai_msg || 'File processed successfully';
            
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderLeftColor = '#4caf50';
            
            alert('✅ File processed successfully!');
        } else {
            resultsContent.textContent = data.message || 'File processing failed';
            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderLeftColor = '#f44336';
            
            alert('❌ ' + (data.message || 'File processing failed'));
        }
    } catch (error) {
        const resultsDiv = document.getElementById('results');
        const resultsContent = document.getElementById('resultsContent');
        resultsContent.textContent = '❌ Error: ' + error.message;
        resultsDiv.classList.remove('hidden');
        resultsDiv.style.borderLeftColor = '#f44336';
    } finally {
        btn.textContent = 'Upload and Process';
        btn.disabled = false;
    }
}

// ============================================
// SIDEBAR TOGGLE WITH BLUR - SIMPLE & CLEAN
// ============================================

function toggleSidebar(event) {
    if (event) {
        event.preventDefault();
    }
    
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const overlay = document.getElementById('overlay');
    const hamburger = document.querySelector('.hamburger-menu');
    
    // Toggle sidebar
    sidebar.classList.toggle('open');
    
    // Add/remove blur and overlay
    if (sidebar.classList.contains('open')) {
        mainContent.classList.add('blur');
        overlay.classList.add('active');
        hamburger.classList.add('active');
    } else {
        mainContent.classList.remove('blur');
        overlay.classList.remove('active');
        hamburger.classList.remove('active');
    }
}

function closeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const overlay = document.getElementById('overlay');
    const hamburger = document.querySelector('.hamburger-menu');
    
    sidebar.classList.remove('open');
    mainContent.classList.remove('blur');
    overlay.classList.remove('active');
    hamburger.classList.remove('active');
}

// ============================================
// DATE AND TIME UPDATE
// ============================================

function updateDateTime() {
    const now = new Date();
    
    // Format time (HH:MM:SS)
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const headerTime = document.getElementById('headerTime');
    if (headerTime) {
        headerTime.textContent = `${hours}:${minutes}:${seconds}`;
    }
    
    // Format date (MM/DD/YYYY)
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const year = now.getFullYear();
    const headerDate = document.getElementById('headerDate');
    if (headerDate) {
        headerDate.textContent = `${month}/${day}/${year}`;
    }
}

// ============================================
// LOAD TRANSACTION HISTORY
// ============================================

async function loadTransactionHistory() {
    try {
        const res = await fetch("/transaction-history");  // ✅ Add await
        const data = await res.json();  // ✅ Add await
        
        if (data.status === 'success') {
            // Insert HTML directly into historyContent
            document.getElementById('historyContent').innerHTML = data.html;
            
            // Setup pagination for tables
            setupTablePagination();
        } else {
            document.getElementById('historyContent').innerHTML = 
                `<p style='color: #e74c3c; text-align: center;'>❌ ${data.message}</p>`;
        }
    } catch (e) {
        document.getElementById('historyContent').innerHTML = 
            `<p style='color: #e74c3c; text-align: center;'>❌ Error: ${e.message}</p>`;
    }
}

// ============================================
// TABLE PAGINATION (Show More)
// ============================================

function setupTablePagination() {
    const tables = document.querySelectorAll('.history-table-section table');
    
    tables.forEach(table => {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const rowsPerPage = 5;  // Show 5 rows initially
        
        if (rows.length <= rowsPerPage) {
            return;  // Don't paginate if less than limit
        }
        
        // Hide rows after the limit
        rows.forEach((row, index) => {
            if (index >= rowsPerPage) {
                row.style.display = 'none';
                row.classList.add('hidden-row');
            }
        });
        
        // Add "Show More" button
        const showMoreBtn = document.createElement('button');
        showMoreBtn.textContent = `📂 Show More (${rows.length - rowsPerPage} more)`;
        showMoreBtn.className = 'btn-show-more';
        showMoreBtn.onclick = function(e) {
            e.preventDefault();
            
            // Show all hidden rows
            tbody.querySelectorAll('.hidden-row').forEach(row => {
                row.style.display = 'table-row';
                row.classList.remove('hidden-row');
            });
            
            // Hide button
            showMoreBtn.style.display = 'none';
        };
        
        // Insert button after table
        table.parentNode.appendChild(showMoreBtn);
    });
}

// Call loadTransactionHistory when history tab is clicked
function switchTab(tabName) {
    // Hide all tabs
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    // Remove active class from nav links
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => link.classList.remove('active'));
    
    // Show selected tab
    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.classList.add('active');
    }
    
    // Add active class to clicked nav link
    if (tabName === 'payments') {
        document.getElementById('navPayments').classList.add('active');
    } else if (tabName === 'history') {
        document.getElementById('navHistory').classList.add('active');
        loadTransactionHistory();  // ✅ Load history when tab is clicked
    } else if (tabName === 'settings') {
        document.getElementById('navSettings').classList.add('active');
    }
    
    // Close sidebar on mobile after clicking nav
    if (window.innerWidth <= 768) {
        closeSidebar();
    }
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
    
