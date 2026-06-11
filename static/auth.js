const API = '';

function toggleForm() {
    document.getElementById('loginForm').classList.toggle('hidden');
    document.getElementById('signupForm').classList.toggle('hidden');
    clearMessages();
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    if(message.includes("per")){
        words = message.split(" ")
        errorDiv.textContent = `Sorry only ${words[0]} attempts are allowed<br>try again after ${words[2]}`;
    }else{
        errorDiv.textContent = message;
    }
    errorDiv.classList.remove('hidden');
    document.getElementById('successMessage').classList.add('hidden');
}

function showSuccess(message) {
    const successDiv = document.getElementById('successMessage');
    successDiv.textContent = message;
    successDiv.classList.remove('hidden');
    document.getElementById('errorMessage').classList.add('hidden');
}

function clearMessages() {
    document.getElementById('errorMessage').classList.add('hidden');
    document.getElementById('successMessage').classList.add('hidden');
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    
    if (!email || !password) {
        showError('❌ Please enter email and password');
        return;
    }
    
    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
        });
        
        const data = await res.json();
        
        if (res.ok) {
            showSuccess('✅ Login successful! Redirecting...');
            setTimeout(() => {
                window.location.href = data.url || '/agent';
            }, 1500);
        } else {
            showError('❌ ' + (data.detail || 'Invalid email or password'));
        }
    } catch (error) {
        showError('❌ Error: ' + error.message);
    }
}

async function handleSignup() {
    const firstName = document.getElementById('firstName').value.trim();
    const lastName = document.getElementById('lastName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const phone = document.getElementById('phone').value.trim();
    const nin = document.getElementById('nin').value.trim();
    const bvn = document.getElementById('bvn').value.trim();
    
    // Validation
    if (!firstName || !lastName || !email || !password || !phone || !nin) {
        showError('❌ Please fill all required fields');
        return;
    }
    
    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showError('❌ Invalid email address or password');
        return;
    }
    
    // Password validation (at least 6 characters)
    if (password.length < 6) {
        showError('❌ Password must be at least 6 characters');
        return;
    }
    
    // Phone validation (basic)
    if (phone.length < 10) {
        showError('❌ Invalid phone number');
        return;
    }
    
    try {
        const res = await fetch('/signup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                first_name: firstName,
                last_name: lastName,
                email,
                password,
                phone_number: phone,
                nin,
                bvn
            })
        });
        
        if (res.ok) {
            showSuccess('✅ Account created successfully! Switching to login...');
            setTimeout(() => {
                toggleForm();
                // Clear signup form
                document.getElementById('firstName').value = '';
                document.getElementById('lastName').value = '';
                document.getElementById('signupEmail').value = '';
                document.getElementById('signupPassword').value = '';
                document.getElementById('phone').value = '';
                document.getElementById('nin').value = '';
                document.getElementById('bvn').value = '';
            }, 1500);
        } else {
            const data = await res.json();
            showError('❌ ' + (data.detail || 'Signup failed'));
        }
    } catch (error) {
        showError('❌ Error: ' + error.message);
    }
}

// Allow Enter key to submit
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('loginEmail').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') handleLogin();
    });
    document.getElementById('loginPassword').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') handleLogin();
    });
    document.getElementById('signupPassword').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') handleSignup();
    });
});
