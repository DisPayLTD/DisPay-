const API = '';
let secret = '';
let userEmail = '';

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

let login, signup, methodOfVerification, enterOtpBox, newPassword,loadingDiv;

document.addEventListener("DOMContentLoaded",()=>{
    login = document.getElementById('loginForm');
    signup = document.getElementById('signup');
    methodOfVerification = document.getElementById("methodOfVerification");
    enterOtpBox = document.getElementById("otp-box");
    newPassword = document.getElementById('changePasswordBox');
    loadingDiv = document.getElementById("loading-overlay");
    
    const view = sessionStorage.getItem("currentWindow");
    toggleForm(view || "loginForm");
})
function toggleForm(name) {
    
    login.classList.toggle('hidden', name !== "loginForm");
    signup.classList.toggle('hidden', name !== "signup");
    methodOfVerification.classList.toggle("hidden", name !== "methodOfVerification");
    enterOtpBox.classList.toggle("hidden", name !== "otp-box");
    newPassword.classList.toggle("hidden",name !== "changePasswordBox");
    
    
    sessionStorage.setItem("currentWindow",name);

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



async function handleLogin() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    
    if (!email || !password) {
        showError('Please enter email and password');
        return;
    }
    
    try {
        loadingDiv.classList.remove("hidden"); 
        const res = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json','X-CSRFToken': getCsrfToken()},
            body: JSON.stringify({email, password})
        });
        
        const data = await res.json();
        
        if (res.ok) {
            
            loadingDiv.classList.add("hidden"); 
            showSuccess('Login successful! Redirecting...');
            setTimeout(() => {
                window.location.href = data.url || '/agent';
            }, 1000);
        } else {
            showError('' + (data.detail || 'Invalid email or password'));
            loadingDiv.classList.add("hidden"); 
        }
    } catch (error) {
        showError('Error: ' + error.message);
        
    } finally{
        loadingDiv.classList.add("hidden"); 
    }
}

// Toggle between Personal and Business Signup
function setAccountType(type) {
    document.getElementById("accountType").value = type;

    document.getElementById("btnTypePersonal").classList.toggle("active", type === "personal");
    document.getElementById("btnTypeBusiness").classList.toggle("active", type === "business");

    const bizFields = document.getElementById("businessFields");
    const isBusiness = type === "business";
    bizFields.classList.toggle("hidden", !isBusiness);
}

// Updated handleSignup function
async function handleSignup() {
    const accountType = document.getElementById('accountType').value;
    const firstName = document.getElementById('firstName').value.trim();
    const lastName = document.getElementById('lastName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const phone = document.getElementById('phone').value.trim();
    const nin = document.getElementById('nin').value.trim();
    const bvn = document.getElementById('bvn').value.trim();
    const dob = document.getElementById('dob').value;
    const gender = document.getElementById('gender').value;
    const address = document.getElementById('address').value.trim();
};

    // Standard Validation
    if (!firstName || !lastName || !email || !password || !phone || !nin ||!dob ||!gender ||! address) {
        showError('Please fill all required personal fields');
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showError('Invalid email address');
        return;
    }

    if (password.length < 6) {
        showError('Password must be at least 6 characters');
        return;
    }

    if (phone.length < 10) {
        showError('Invalid phone number');
        return;
    }

    // --- PERSONAL SIGNUP ROUTE ---
    if (accountType === 'personal') {
        try {
            loadingDiv.classList.remove("hidden");
            const res = await fetch('/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    email:email,
                    password: password,
                    phone_number: phone,
                    nin:nin,
                    bvn: bvn,
                    dob:dob,
                    address: address,
                    gender: gender 
                })
            });
            const data = await res.json();

            if (data.status === 'success') {
                showSuccess('Account created successfully! Switching to login...');
                setTimeout(() => {
                    toggleForm("loginForm");
                    clearSignupForm();
                }, 1500);
            } else {
                showError('' + (data.detail || data.message || 'Signup failed'));
            }
        } catch (error) {
            showError('Error: ' + error.message);
        } finally {
            loadingDiv.classList.add("hidden");
        }
        return;
    }

    // --- BUSINESS SIGNUP ROUTE ---
    if (accountType === 'business') {
        const orgName = document.getElementById('orgName').value.trim();
        const cac = document.getElementById('cac').value.trim();
        const regType = document.getElementById('regType').value;
        const tin = document.getElementById('tin').value.trim();

        if (!orgName || !cac || !tin) {
            showError('Please fill in Business Name, CAC, and TIN fields');
            return;
        }

        try {
            loadingDiv.classList.remove("hidden");

            // Step 1: Verify CAC & TIN first
            const verifyRes = await fetch('/verify-cac-tin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ cac, tin, reg_type: regType })
            });
            const verifyData = await verifyRes.json();

            if (!verifyRes.ok || verifyData.status !== 'success') {
                showError(verifyData.detail || verifyData.message || 'CAC or TIN verification failed');
                loadingDiv.classList.add("hidden");
                return;
            }

            // Step 2: Proceed with Business Onboarding
            const onboardRes = await fetch('/onboard-new-business', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    email,
                    password,
                    phone_number: phone,
                    nin,
                    bvn,
                    name: orgName,
                    cac: `${regType}-${cac}`,
                    tin: tin
                })
            });
            const onboardData = await onboardRes.json();

            if (onboardData.status === 'success') {
                showSuccess('Business registered successfully!');
                setTimeout(() => {
                    window.location.href = onboardData.url || '/dashboard';
                }, 1200);
            } else {
                showError('' + (onboardData.detail || onboardData.message || 'Business onboarding failed'));
            }
        } catch (error) {
            showError('Error: ' + error.message);
        } finally {
            loadingDiv.classList.add("hidden");
        }
    }
}

function clearSignupForm() {
    document.getElementById('firstName').value = '';
    document.getElementById('lastName').value = '';
    document.getElementById('signupEmail').value = '';
    document.getElementById('signupPassword').value = '';
    document.getElementById('phone').value = '';
    document.getElementById('nin').value = '';
    document.getElementById('bvn').value = '';
    document.getElementById('orgName').value = '';
    document.getElementById('cac').value = '';
    document.getElementById('tin').value = '';
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

let time_otp_sent = "";

const sendOtpBtn = document.getElementById("send-otp-btn");
const otpMsg = document.getElementById("otpMsg");

async function sendOtp(){
    
    try {
        loadingDiv.classList.remove("hidden"); 
        const email = document.getElementById("userEmail").value;
        if(!email){
            alert("Please enter email");
            return;
        }
        
        const payload = {user_email:email}
        const res = await fetch("/send-otp",{
            method:"POST",
            headers: {"Content-Type":"application/json",'X-CSRFToken': getCsrfToken()},
            body:JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if(data.status === `success`){

            otpMsg.innerText = data.message;
            showSuccess("OTP is successfully sent to your email");
            toggleForm("otp-box");
            
            
            secret = data.secret
            time_otp_sent = data.created_at;
            
        }
    } catch (error) {
        showError('Error sending OTP: ' + error.message);
    } finally{
        loadingDiv.classList.add("hidden"); 
    }
}

const inputs = document.querySelectorAll(".code-box");
    inputs.forEach((file,index) =>{
        file.addEventListener("input",(e)=>{
            const value = e.target.value;
            if(value.length > 0 && index < inputs.length -1){
            inputs[index +1].focus()
            }
            
        });
        
        file.addEventListener("keydown",(e)=>{
              
               if(e.key==="Backspace" && file.value === "" && index >0){
                   inputs[index - 1].focus();
               } 
            });
    });
const verifyBtn = document.getElementById("verify-btn");

verifyBtn.addEventListener("click",async ()=>{
        try{
            loadingDiv.classList.remove("hidden"); 
            verifyBtn.disabled = true
            verifyBtn.innerText = `Verifying...`;
            await verifyOtp()
            
        }catch(error) {
            alert(`error: ${String(error)}`);
        }finally{
            verifyBtn.disabled = false
            verifyBtn.innerText = `Verify`
            loadingDiv.classList.add("hidden"); 
        }
    })


async function verifyOtp(){
    try {
        const elements = document.getElementsByClassName("code-box");
        const otp = Array.from(elements, el => el.value.trim()).join("");
        const email = document.getElementById("userEmail").value;
        const payload = {otp: otp, email: email,secret:secret, created_at:time_otp_sent};

        const res = await fetch("/verify-otp",{
            method: "POST",
            headers: {"Content-Type": "application/json", 'X-CSRFToken': getCsrfToken()},
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if(data.status === `success`){
            // i created this to send it to veriyOtp route
            userEmail = email;
            
            showSuccess('OTP verified successfully!');
            toggleForm("changePasswordBox");
            
        } else {
            
            if(data.message && data.message.includes("Invalid")){
                showError(data.message);
                return;
            }
            
            showError(data.message || 'Verification failed');
            toggleForm("otpBox");
        }
    } catch (error) {
        showError('Error verifying OTP: ' + error.message);
    }
}

async function changePassword(){
    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;
    
     if(newPassword != confirmPassword){
            showError("Passwords do not match");
            return;
        }
    
    try{
        loadingDiv.classList.remove("hidden"); 
        payload = {user_email:userEmail,new_password:newPassword}
        const res = await fetch("/change-password",{
            headers :{"Content-Type":"application/json","X-CSRFToken": getCsrfToken()},
            method:"POST",
            body:JSON.stringify(payload)
        })
        const data = await res.json()
    
        if(data.status === `success`){
            showSuccess("password change successfully");
            toggleForm("loginForm");
        }else {
            showError(data.message);
        }
    } catch (error){
        console.log(String(error))
    } finally {
        loadingDiv.classList.add("hidden"); 
    }
}
document.addEventListener("DOMContentLoaded",()=>{
    const currentView = sessionStorage.getItem("currentWindow");
    toggleForm(currentView);
});

function payrollServices(){
    window.location.href = "/payroll-services"
}
