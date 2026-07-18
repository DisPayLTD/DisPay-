const API = '';

function getCsrfToken(){
    const value = `; ${document.cookie}`;
    const data = value.split("; csrftoken=");
    if(data.length === 2){
        const res = data.pop().split(";").shift();
        return res;
    } else{
        return "";
    }
}

function toggleForm() {
    document.getElementById('loginForm').classList.toggle('hidden');
    document.getElementById('signupForm').classList.toggle('hidden');
    document.getElementById('forgotPass').classList.toggle('hidden')
    clearMessages();
}


// ==========================================
// 1. AUTOMATIC FONT AWESOME LOADER
// ==========================================
if (!document.querySelector('link[href*="font-awesome"]')) {
    const fontAwesome = document.createElement('link');
    fontAwesome.rel = 'stylesheet';
    fontAwesome.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css';
    document.head.appendChild(fontAwesome);
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    if(message.includes("per")){
        errorDiv.innerHTML = `<i class="fa-solid fa-check" style="margin-right: 8px;"></i> Sorry try again later`;
    }else{
        
        errorDiv.innerHTML = `<i class="fa-solid fa-circle-xmark" style="margin-right: 8px;"></i>${message}`;
    }
    errorDiv.classList.remove('hidden');
    document.getElementById('successMessage').classList.add('hidden');
}


// ==========================================
//  SHOWSUCCESS FUNCTION
// ==========================================
function showSuccess(message) {
    const successDiv = document.getElementById('successMessage');
    
    successDiv.innerHTML = `<i class="fa-solid fa-check" style="margin-right: 8px;"></i>${message}`;
    
    // Display the success message and hide the error message
    successDiv.classList.remove('hidden');
    
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.classList.add('hidden');
    }
}


function clearMessages() {
    document.getElementById('errorMessage').classList.add('hidden');
    document.getElementById('successMessage').classList.add('hidden');
}

async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    
    if (!email || !password) {
        showError('Please enter email and password');
        return;
    }
    
    try {
        const res = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json','X-CSRFToken': getCsrfToken()},
            body: JSON.stringify({email, password})
        });
        
        const data = await res.json();
        
        if (res.ok) {
            showSuccess('Login successful! Redirecting...');
            setTimeout(() => {
                window.location.href = data.url || '/agent';
            }, 1000);
        } else {
            showError('' + (data.detail || 'Invalid email or password'));
        }
    } catch (error) {
        showError('Error: ' + error.message);
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
        showError('Please fill all required fields');
        return;
    }
    
    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showError('Invalid email address or password');
        return;
    }
    
    // Password validation (at least 6 characters)
    if (password.length < 6) {
        showError('Password must be at least 6 characters');
        return;
    }
    
    // Phone validation (basic)
    if (phone.length < 10) {
        showError('Invalid phone number');
        return;
    }
    
    try {
        const res = await fetch('/signup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json','X-CSRFToken': getCsrfToken()},
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
        const data = await res.json();
        
        if (data.status === `success`) {
            showSuccess('Account created successfully! Switching to login...');
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
            showError('' + (data.detail || data.message || 'Signup failed'));
        }
    } catch (error) {
        showError('Error: ' + error.message);
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

//otp section

let time_otp_sent = ""
const enterOtpBox = document.getElementByClassName("otp-box")[0];
const sendOtpBtn = document.getElementById("send-otp-btn");

const forgotPass = document.getElementById(forgotPass).addEventListener("click",()=>{
    login
})
function sendOtp(){
    const res = fetch("/send_otp");
    data = res.json();
    if(data.status === `success`){
        setTimeout(showSuccess,5000,data.message);
        sendOtpBtn.classList.add("hidden");
        time_otp_sent = data.created_at
        enterOtpBox.classList.remove("hidden");
    }
}

function verifyOtp(){
    const elements = document.getElementByClassName("code-box");
    otp = Array.from(elements,el => el.value.trim()).join(",");
    payload = {otp:otp,created_at:time_otp_sent}
    
    const res = fetch("/verify-otp",{
        method:"POST",
        headers: {"Content-Type":"application/json"},
        json = JSON.stringify(payload);
    });
    const data = res.json()
    if(data.status === `succcess`){
        enterOtpBox.classList.add("hidden");
        changePassword.classList.remove("hidden");
    }else{
        if("Invalid" in data.message){
            alert(data.message);
            return;
        }
        changePassword.classList.add("hidden");
        alert(data.message)
        sentOtpBox.classList.remove("hidden");
    }
}
