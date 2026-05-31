const API = '';

let userEmail = '';
let isAuthenticated = false;

// Step 1: Send OTP
async function sendOTP() {
    userEmail = document.getElementById('email').value;
    
    if (!userEmail) {
        alert('Please enter email');
        return;
    }
    
    try {
        const res = await fetch('/send-otp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: userEmail})
        });
        
        const data = await res.json();
        
        if (data.status === 'success') {
            document.getElementById('emailSection').classList.add('hidden');
            document.getElementById('otpSection').classList.remove('hidden');
            document.getElementById('status').textContent = '⏳ Waiting for OTP verification';
            alert(`your otp is ${data.otp}`);
            
        } else {
            alert('❌ ' + data.message);
        }
    } catch (error) {
        alert('❌ Error: ' + data.message);
    }
}

// Step 2: Verify OTP
async function verifyOTP() {
    const otp = document.getElementById('otp').value;
    
    if (!otp || otp.length !== 6) {
        alert('Please enter 6-digit OTP');
        return;
    }
    
    try {
        const res = await fetch('/verify-otp', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: userEmail, otp: otp})
        });
        
        const data = await res.json();
        
        if (data.authenticated) {
            isAuthenticated = true;
            document.getElementById('otpSection').classList.add('hidden');
            document.getElementById('paymentSection').classList.remove('hidden');
            document.getElementById('status').textContent = '✅ Authenticated - Ready to pay';
            alert('✅ OTP verified successfully!');
        } else {
            alert('❌ ' + data.message);
        }
    } catch (error) {
        alert('❌ Error: ' + error);
    }
}

// Step 3: Execute Payment
async function executePayment() {
    if (!isAuthenticated) {
        alert('❌ Not authenticated. Verify OTP first');
        return;
    }
    
    const command = document.getElementById('command').value;
    
    if (!command) {
        alert('Please enter payment command');
        return;
    }
    
    const btn = event.target;
    btn.textContent = 'Processing...';
    btn.disabled = true;
    
    try {
        const res = await fetch('/send-money', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({command: command})
        });
        
        const data = await res.json();
        
        const resultsDiv = document.getElementById('results');
        const resultsContent = document.getElementById('resultsContent');
        
        if (data.status === 'success') {
            resultsContent.innerHTML = data.html_table;
            resultsDiv.classList.remove('hidden', 'error');
            resultsDiv.classList.add('success');
        } else {
            resultsContent.textContent = data.message;
            resultsDiv.classList.remove('hidden', 'success');
            resultsDiv.classList.add('error');
        }
    } catch (error) {
        alert('❌ Error: ' + error);
    } finally {
        btn.textContent = 'Execute Payment';
        btn.disabled = false;
    }
}
