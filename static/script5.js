
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
            const accountNumber = document.getElementById('accountNumber').value.trim();
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
                    showToast('Account not found. Check details.', 'error');
                    hideAccountNameDisplay();
                }
            })
            .catch(error => {
                console.error('Resolution error:', error);
                display.classList.remove('loading');
                showToast('Verification failed. Try again.', 'error');
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
                showToast('Please fill all fields', 'error');
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
            showToast('Recipient added!', 'success');
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
            showToast('Recipient removed', 'success');
        };

        // Send payments
        document.getElementById('sendBtn').addEventListener('click', () => {
            if (recipients.length === 0) {
                showToast('No recipients added', 'error');
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
            showToast(`${recipients.length} payment(s) ready to send!`, 'success');

            // Here you would send to your backend
            // await fetch('/api/bulk-payments', { method: 'POST', body: JSON.stringify(payload) })
        });

        // Toast
        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = type;
            toast.style.display = 'block';

            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        }

        // Initialize
        updateRecipientsList();