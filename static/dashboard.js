const API = '';
let userEmail = '';
let isAuthenticated = true;
let pendingPaymentData = null;
const loadingDiv = document.getElementById("loading-overlay");

function getCsrfToken(){
    const value = `; ${document.cookie}`;
    const data = value.split("; csrftoken=")
    if(data.length === 2){
        const res = data.pop().split(";").shift()
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


if (!document.querySelector('link[href*="font-awesome"]')) {
    const fontAwesome = document.createElement('link');
    fontAwesome.rel = 'stylesheet';
    fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
    document.head.appendChild(fontAwesome);
}

function getToastContainer() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}

function showToast(message, type = 'success', duration = 4200) {
    const container = getToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? 'fa-check' : 'fa-circle-xmark';
    toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        toast.addEventListener('animationend', () => toast.remove());
    }, duration);
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    if (message.includes("per")) {
        //showToast("Sorry try again later", 'error');
        showToast(message, 'error');
    } else {
        showToast(message, 'error');
    }
}


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
    //document.getElementById('walletBalance').textContent = (user.wallet_balance || 0).toFixed(2);
    if (user.has_wallet){
        fetchBalance();
    }

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
    setInterval(async () => {
        try{
            const res = await fetch("/account-balance");
            const data = await res.json();
            if(data.status === "success"){
                const balance = data.balance || 0.00;
                document.getElementById('walletBalance').textContent = balance.toFixed(2);
            }
        }catch(error){
            console.log("Balance fetch error:", error);
        }
    }, 5000);  // 5000ms = 5 seconds ✓
}


// ============================================
// TAB SWITCHING
// (renamed to baseSwitchTab so enhancedSwitchTab
//  below can safely call it without recursing
//  into itself once `switchTab` is reassigned)
// ============================================

function baseSwitchTab(tabName) {
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

// `switchTab` starts out pointing at the base implementation.
// Further down, this gets reassigned to `enhancedSwitchTab`.
let switchTab = baseSwitchTab;

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
        showError('❌ Not authenticated. Please login first');
        return;
    }

    const command = document.getElementById('command').value;

    if (!command.trim()) {
        showError('❌ Please enter a payment command');
        return;
    }

    const idempotency_key = `DISPAY-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const paymentData = {
        command: command,
        idempotency_key: idempotency_key
    };

    // Show PIN modal (user enters PIN)
    showPinModal(paymentData);

    return;
}

function showPinModal(paymentData) {
    pendingPaymentData = paymentData;
    document.getElementById('pinModal').style.display = 'flex';
}

async function submitPin() {
    const pinInputs = document.querySelectorAll('.pin-modal-input');
    const pin = Array.from(pinInputs).map(i => i.value).join('');

    if (pin.length !== 4) {
        showPinError('Please enter a 4-digit PIN');
        return;
    }
    pendingPaymentData.pin = pin;

    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    const successTransfers = document.getElementById("successTransfer");
    const failedTransfers = document.getElementById("failedTransfers");

    loadingDiv.classList.remove("hidden");

    try {
        const res = await fetch('/send-money', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(pendingPaymentData)
        });

        const data = await res.json();

        if (data.status === 'success') {
            loadingDiv.classList.add("hidden");
            successTransfers.innerHTML = data.success_html_table || '<p>No successful transfers</p>';
            failedTransfers.innerHTML = data.failed_html_table || '<p>No failed transfers</p>';
            resultsContent.innerHTML = data.ai_msg || 'Payment processed successfully';

            resultsDiv.classList.remove('hidden');
            resultsDiv.style.borderLeftColor = '#4caf50';

            closePinModal();
        } else {
            loadingDiv.classList.add("hidden");
            showPinError(data.message || 'Payment failed');
        }
    } catch (error) {
        showPinError('Error: ' + error.message);
    } finally {
        loadingDiv.classList.add("hidden");
    }
}

function showPinError(msg) {
    document.getElementById('pinError').textContent = msg;
    document.getElementById('pinError').style.display = 'block';
}

function closePinModal() {
    document.getElementById('pinModal').style.display = 'none';
    document.querySelectorAll('.pin-modal-input').forEach(i => i.value = '');
    document.getElementById('pinError').style.display = 'none';
    pendingPaymentData = null;
}
function cancelPin() {
    closePinModal();
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
// BALANCE VISIBILITY TOGGLE (NEW)
// ============================================
let isBalanceVisible = true;

function toggleBalanceVisibility() {
    isBalanceVisible = !isBalanceVisible;
    const balanceDisplay = document.getElementById('balanceDisplay');
    const toggleIcon = document.getElementById('balanceToggle');

    if (isBalanceVisible) {
        balanceDisplay.style.filter = 'none';
        toggleIcon.className = 'fa-solid fa-eye';
    } else {
        balanceDisplay.style.filter = 'blur(8px)';
        toggleIcon.className = 'fa-solid fa-eye-slash';
    }
}

// ============================================
// FOCUS AI BOX (NEW)
// ============================================
function focusAIBox() {
    switchTab('home');
    setTimeout(() => {
        const aiTextarea = document.getElementById('command');
        if (aiTextarea) {
            aiTextarea.focus();
            aiTextarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 300);
}

// ============================================
// TRIGGER FILE UPLOAD (NEW)
// ============================================
function triggerFileUpload() {
    const fileInput = document.getElementById('paymentFile');
    if (fileInput) {
        fileInput.click();
    }
}

// ============================================
// BULK PAYMENT (NEW)
// ============================================

        const BANK_CODES = {
            'Access Bank': '025',
            'Zenith Bank': '057',
            'GTBank': '058',
            'First Bank': '011',
            'UBA': '033',
            'FCMB': '214',
            'Stanbic IBTC': '221',
            'Wema Bank': '035',
            'Fidelity Bank': '070',
            'Standard Chartered': '068',
            'Ecobank': '050',
            'Polaris Bank': '076',
            'Unite Bank': '079',
            'Interswitch NUBAN': '100',
            'Providus Bank': '101'
        };

        let recipients = [];
        let resolutionTimeout;

        // Account number input - trigger resolution as user types
        document.getElementById('accountNumber').addEventListener('input', (e) => {
            clearTimeout(resolutionTimeout);
            const accountNumber = e.target.value.trim();
            const bankSelect = document.getElementById('bankSelect').value;

            if (accountNumber.length >= 10 && bankSelect) {
                resolveAccountName(accountNumber, bankSelect);
            } else {
                hideAccountNameDisplay();
            }
        });

        // Bank selection change
        document.getElementById('bankSelect').addEventListener('change', (e) => {
            const accountNumber = document.getElementById('accountNumber')?.value.trim();
            console.log(accountNumber || "no account number");
            if (accountNumber.length >= 10 && e.target.value) {
                resolveAccountName(accountNumber, e.target.value);
            }
        });

        // Resolve account name from NUBAN API (free)
        function resolveAccountName(accountNumber, bankName) {
            const bankCode = BANK_CODES[bankName];
            if (!bankCode) return;

            const display = document.getElementById('accountNameDisplay');
            display.classList.add('loading', 'visible');
            display.textContent = 'Verifying...';

            // Use NUBAN API (free)
            fetch(`/verify-bank-account`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    account_number: accountNumber,
                    bank_code: bankCode
                })
            })
            .then(res => res.json())
            .then(data => {
                display.classList.remove('loading')
                
                if (data.status === 'success' || data.account_name) {
                    const name = data.account_name || data.data?.account_name || 'Account verified';
                    display.textContent = name;
                    display.style.opacity = '1';
                } else {
                    showError('Account not found. Check details.');
                    hideAccountNameDisplay();
                }
            })
            .catch(error => {
                console.error('Resolution error:', error);
                display.classList.remove('loading');
                showError('Verification failed. Try again.');
                hideAccountNameDisplay();
            });
        }

        function hideAccountNameDisplay() {
            const display = document.getElementById('accountNameDisplay');
            display.classList.remove('visible', 'loading');
            display.textContent = '';
        }

        // Add recipient
        document.getElementById('addBtn').addEventListener('click', () => {
            const accountNumber = document.getElementById('accountNumber').value.trim();
            const bankName = document.getElementById('bankSelect').value;
            const accountName = document.getElementById('accountNameDisplay').textContent;
            const amount = document.getElementById('amount').value;

            
            if (!accountNumber || !bankName || !amount) {
                showError('Please fill all fields');
                return;
            }

            // Add to recipients array
            recipients.push({
                id: Date.now(),
                accountNumber,
                bankName,
                accountName,
                bankCode: BANK_CODES[bankName],
                amount: parseFloat(amount)
            });

            // Clear form
            document.getElementById('recipientForm').reset();
            hideAccountNameDisplay();

            // Update UI
            updateRecipientsList();
            showSuccess('Recipient added!', 'success'); 
        });

        // Update recipients list display
        function updateRecipientsList() {
            const container = document.getElementById('recipientsContainer');
            const list = document.getElementById('recipientsList');
            const emptyState = document.getElementById('emptyState');
            const sendBtn = document.getElementById('sendBtn');
            const count = document.getElementById('recipientCount');

            count.textContent = recipients.length;

            if (recipients.length === 0) {
                list.style.display = 'none';
                emptyState.style.display = 'block';
                sendBtn.style.display = 'none';
                return;
            }

            emptyState.style.display = 'none';
            list.style.display = 'block';
            sendBtn.style.display = 'flex';

            container.innerHTML = recipients.map(recipient =>`
                <div class="recipient-item">
                    <div class="recipient-details">
                        <div class="recipient-name">${recipient.accountName}</div>
                        <div class="recipient-info">${recipient.accountNumber} • ${recipient.bankName}</div>
                        <div class="recipient-amount">₦${parseFloat(recipient.amount).toLocaleString('en-NG', { minimumFractionDigits: 2 })}</div>
                    </div>
                    <button type="button" class="btn-remove" onclick="removeRecipient(${recipient.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `).join('');
        }

        // Remove recipient
        window.removeRecipient = (id) => {
            recipients = recipients.filter(r => r.id !== id);
            updateRecipientsList();
            showSuccess('Recipient removed');
        };

        // Send payments
        document.getElementById('sendBtn').addEventListener('click', () => {
            if (recipients.length === 0) {
                showError('No recipients added', 'error');
                return;
            }

            // Prepare payload
            const payload = {
                batchId: `BATCH-${Date.now()}`,
                timestamp: new Date().toISOString(),
                totalRecipients: recipients.length,
                totalAmount: recipients.reduce((sum, r) => sum + r.amount, 0),
                recipients: recipients.map(r => ({
                    accountName: r.accountName,
                    accountNumber: r.accountNumber,
                    bankCode: r.bankCode,
                    bankName: r.bankName,
                    amount: r.amount
                }))
            };

            console.log('Payment payload:', payload);
            showSuccess(`${recipients.length} payment(s) ready to send!`);

            // Here you would send to your backend
            // await fetch('/api/bulk-payments', { method: 'POST', body: JSON.stringify(payload) })
        });

        // Initialize
        updateRecipientsList();


// ============================================
// BUY AIRTIME (NEW)
// ============================================
function buyAirtime() {
    const network = document.getElementById('airtimeNetwork').value;
    const phone = document.getElementById('airtimePhone').value;
    const amount = document.getElementById('airtimeAmount').value;

    if (!network || !phone || !amount) {
        showError('Please fill all fields');
        return;
    }

    if (phone.length !== 11) {
        showError('Invalid phone number');
        return;
    }

    if (amount < 50) {
        showError('Minimum amount is ₦50');
        return;
    }

    showSuccess(`Airtime purchase feature coming soon! ${network} - ${phone} - ₦${amount}`);
}

// ============================================
// BUY DATA (NEW)
// ============================================
function buyData() {
    const network = document.getElementById('dataNetwork').value;
    const phone = document.getElementById('dataPhone').value;
    const plan = document.getElementById('dataPlan').value;

    if (!network || !phone || !plan) {
        showError('Please fill all fields');
        return;
    }

    if (phone.length !== 11) {
        showError('Invalid phone number');
        return;
    }

    showSuccess(`Data purchase feature coming soon! ${network} - ${phone} - ${plan}`);
}

// ============================================
// BUY ELECTRICITY (NEW)
// ============================================
function buyElectricity() {
    const disco = document.getElementById('electricityDisco').value;
    const meterType = document.getElementById('meterType').value;
    const meterNumber = document.getElementById('meterNumber').value;
    const amount = document.getElementById('electricityAmount').value;

    if (!disco || !meterType || !meterNumber || !amount) {
        showError('Please fill all fields');
        return;
    }

    if (amount < 500) {
        showError('Minimum amount is ₦500');
        return;
    }

    showSuccess(`Electricity payment coming soon! ${disco} - ${meterType} - ${meterNumber} - ₦${amount}`);
}

// ============================================
// NOTIFICATION BADGE UPDATE (NEW)
// ============================================
function updateNotificationBadge(count) {
    const badges = document.querySelectorAll('.notification-badge');
    badges.forEach(badge => {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'block' : 'none';
    });
}

// ============================================
// LOAD TRANSACTION HISTORY
// ============================================

async function loadTransactionHistory() {
    try {
        const res = await fetch("/transaction-history");
        const data = await res.json();

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


// Auto-focus PIN inputs
document.querySelectorAll('.pin-modal-input').forEach((input, index) => {
    input.addEventListener('input', (e) => {
        if (e.target.value && index < 3) {
            document.querySelectorAll('.pin-modal-input')[index + 1].focus();
        }
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && index > 0) {
            document.querySelectorAll('.pin-modal-input')[index - 1].focus();
        }
    });
});

async function loadRecentTransactions() {
    try {
        const res = await fetch("/transaction-history");
        const data = await res.json();

        if (data.status === 'success') {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = data.html;

            const allRows = tempDiv.querySelectorAll('tbody tr');
            const recentRows = Array.from(allRows).slice(0, 5);

            if (recentRows.length > 0) {
                let html = '<div class="transaction-items">';
                recentRows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        html += `
                            <div class="transaction-item">
                                <div class="transaction-icon">
                                    <i class="fa-solid fa-arrow-right"></i>
                                </div>
                                <div class="transaction-details">
                                    <h4>${cells[0].textContent}</h4>
                                    <p>${cells[1].textContent}</p>
                                </div>
                                <div class="transaction-amount">
                                    ₦${cells[2].textContent}
                                </div>
                            </div>
                        `;
                    }
                });
                html += '</div>';
                document.getElementById('recentTransactions').innerHTML = html;
            } else {
                document.getElementById('recentTransactions').innerHTML =
                    '<p class="empty-state">No recent transactions</p>';
            }
        }
    } catch (e) {
        console.error('Error loading recent transactions:', e);
    }
}

// ============================================
// ENHANCED POPULATE DASHBOARD (NEW)
// ============================================
function enhancedPopulateDashboard(user) {
    // Sidebar profile
    const initial = user.first_name.charAt(0).toUpperCase() || 'U';
    const sidebarInitial = document.getElementById('sidebarInitial');
    const sidebarName = document.getElementById('sidebarName');
    const sidebarEmail = document.getElementById('sidebarEmail');

    if (sidebarInitial) sidebarInitial.textContent = initial;
    if (sidebarName) sidebarName.textContent = `${user.first_name} ${user.last_name}`;
    if (sidebarEmail) sidebarEmail.textContent = user.email;

    // Greeting
    const hour = new Date().getHours();
    let greeting = 'Hi';
    if (hour < 12) greeting = 'Good Morning';
    else if (hour < 17) greeting = 'Good Afternoon';
    else greeting = 'Good Evening';

    const greetingText = document.getElementById('greetingText');
    if (greetingText) greetingText.textContent = `${greeting}, ${user.first_name} 👋`;

    // Profile tab
    const profileName = document.getElementById('profileName');
    const profileEmail = document.getElementById('profileEmail');
    const profilePhone = document.getElementById('profilePhone');
    const profileNIN = document.getElementById('profileNIN');
    const profileBVN = document.getElementById('profileBVN');

    if (profileName) profileName.textContent = `${user.first_name} ${user.last_name}`;
    if (profileEmail) profileEmail.textContent = user.email;
    if (profilePhone) profilePhone.textContent = user.phone_number || '-';
    if (profileNIN) profileNIN.textContent = user.nin || '-';
    if (profileBVN) profileBVN.textContent = user.bvn || '-';

    // Show employer-only elements
    if (user.is_employer) {
        document.querySelectorAll('.employer-only').forEach(el => {
            el.style.display = '';
        });
    }
}

// ============================================
// ENHANCED LOAD USER DATA (WRAPPER)
// ============================================
async function enhancedLoadUserData() {
    try {
        const res = await fetch('/get-user-data');
        const data = await res.json();

        if (data.status === 'success') {
            populateDashboard(data.user);
            enhancedPopulateDashboard(data.user);
        } else {
            window.location.href = data.url || '/auth';
        }
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

// ============================================
// AUTO-SCROLL TO RESULTS (NEW)
// ============================================
function scrollToResults() {
    const resultsDiv = document.getElementById('results');
    if (resultsDiv && !resultsDiv.classList.contains('hidden')) {
        setTimeout(() => {
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
    }
}

// ============================================
// ENHANCED SWITCH TAB (WRAPPER FOR YOUR EXISTING)
// FIXED: now calls baseSwitchTab() directly instead of
// switchTab() — previously this called itself forever
// once `switchTab` was reassigned below, causing a stack
// overflow / blank page on every nav click.
// ============================================
function enhancedSwitchTab(tabName) {
    // Call the original tab-switching logic (renamed to avoid recursion)
    baseSwitchTab(tabName);

    // Additional enhancements
    const tabs = document.querySelectorAll('.tab-content');
    tabs.forEach(tab => tab.classList.remove('active'));

    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.classList.add('active');
    }

    // Update bottom nav
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => item.classList.remove('active'));

    if (tabName === 'home') {
        const navHome = document.getElementById('navHome');
        if (navHome) navHome.classList.add('active');
    } else if (tabName === 'history') {
        const navHistory = document.getElementById('navHistory');
        if (navHistory) navHistory.classList.add('active');
        loadTransactionHistory();
    } else if (tabName === 'profile') {
        const navProfile = document.getElementById('navProfile');
        if (navProfile) navProfile.classList.add('active');
    }

    // Close sidebar
    closeSidebar();

    // Scroll to top
    const mainContent = document.querySelector('.main-content');
    if (mainContent) mainContent.scrollTo(0, 0);
}

// Safe now: enhancedSwitchTab no longer calls itself through this reassignment
switchTab = enhancedSwitchTab;

// ============================================
// INITIALIZE NEW FEATURES ON DOM LOAD
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Load recent transactions
    loadRecentTransactions();
    setInterval(loadRecentTransactions, 30000);

    // Enhanced user data load
    enhancedLoadUserData();

    // File upload handler
    const fileInput = document.getElementById('paymentFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                uploadFile({ preventDefault: () => {} });
            }
        });
    }

    // Initialize notification badge
    updateNotificationBadge(0);

    // Initialize with home tab
    const navHome = document.getElementById('navHome');
    if (navHome) navHome.classList.add('active');
});
