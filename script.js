// Bank codes mapping
        const BANK_CODES = {
            'UBA': '033',
            'Access Bank': '044',
            'GTBank': '058',
            'First Bank': '011',
            'Zenith Bank': '057',
            'Ecobank': '050',
            'Fidelity Bank': '070',
            'Union Bank': '032',
            'Stanbic IBTC': '031',
            'FCMB': '214',
            'Wema Bank': '035',
            'Heritage Bank': '030',
            'Keystone Bank': '082',
            'Providus Bank': '101',
            'Polaris Bank': '076'
        };

        let recipientCount = 0;
        let recipients = []
        // Initialize
        document.addEventListener('DOMContentLoaded',function() {
            updateEmptyState();
        });

        function addRecipient() {
            recipientCount++;
            
            const container = document.getElementById('recipientsContainer');
            
            // Row 1: Account Name and Number
            const row1 = document.createElement('tr');
            row1.className = 'row-main';
            row1.id = `recipient-${recipientCount}-row1`;
            row1.innerHTML = `
                <td>
                    <div class="table-label">Account Name</div>
                    <input type="text" placeholder="e.g., John Doe" class="table-input account-name" id="name-${recipientCount}" onchange="checkVerifyButton(${recipientCount})">
                </td>
                <td>
                    <div class="table-label">Account Number</div>
                    <input type="text" placeholder="e.g., 1234567890" class="table-input account-number" id="number-${recipientCount}" onchange="checkVerifyButton(${recipientCount})">
                </td>
                <td>
                    <div class="table-label">Amount</div>
                    <input type="text" placeholder="e.g., 1000" class="table-input amount" id="amount-${recipientCount}">
                </td>
                <td class="table-col-actions" rowspan="1">
                    <div class="table-actions">
                        <button class="btn-remove" onclick="removeRecipient(${recipientCount})">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            `;

            // Row 2: Bank, Bank Code, and Verify
            const row2 = document.createElement('tr');
            row2.className = 'row-secondary';
            row2.id = `recipient-${recipientCount}-row2`;
            row2.innerHTML = `
                <td>
                    <div class="table-label">Bank Name</div>
                    <select class="table-select bank-select" id="bank-${recipientCount}" onchange="updateBankCode(${recipientCount})">
                        <option value="">Select bank</option>
                        ${Object.keys(BANK_CODES).map(bank => `<option value="${bank}">${bank}</option>`).join('')}
                    </select>
                </td>
                <td>
                    <div class="table-label">Bank Code</div>
                    <div class="bank-code-cell bank-code-empty" id="code-display-${recipientCount}">-</div>
                </td>
            `;

            container.appendChild(row1);
            container.appendChild(row2);
            
            // Add verify button in a separate row if needed
            const row3 = document.createElement('tr');
            row3.className = 'row-verify';
            row3.id = `recipient-${recipientCount}-row3`;
            row3.innerHTML = `
                <td colspan="2">
                    <div id="verify-cell-${recipientCount}" style="display: flex; gap: 10px;">
                        <button class="btn-verify" id="verify-btn-${recipientCount}" onclick="verifyAccount(${recipientCount})" style="display: none;">
                            <i class="fas fa-check"></i> Verify Account
                        </button>
                    </div>
                </td>
                <td></td>
            `;
            container.appendChild(row3);
            
            document.getElementById('tableWrapper').style.display = 'block';
            updateEmptyState();
        }
        
        
        //remove recipient function 
        function removeRecipient(id) {
            document.getElementById(`recipient-${id}-row1`).remove();
            document.getElementById(`recipient-${id}-row2`).remove();
            document.getElementById(`recipient-${id}-row3`).remove();
            const ind = recipients.findIndex(rec => rec.id === id);
            recipients.splice(ind,1);
            recipientCount--;
            updateEmptyState();
        }

        function updateBankCode(id) {
            const bankSelect = document.getElementById(`bank-${id}`);
            const selectedBank = bankSelect.value;
            const codeDisplay = document.getElementById(`code-display-${id}`);

            if (selectedBank && BANK_CODES[selectedBank]) {
                const bankCode = BANK_CODES[selectedBank];
                codeDisplay.textContent = bankCode;
                codeDisplay.classList.remove('bank-code-empty');
                codeDisplay.style.color = '#667eea';
            } else {
                codeDisplay.textContent = '-';
                codeDisplay.classList.add('bank-code-empty');
            }

            // Reset verification when bank changes
            resetVerification(id);
            checkVerifyButton(id);
        }
        
        //check verify btn
        function checkVerifyButton(id) {
            const name = document.getElementById(`name-${id}`).value.trim();
            const number = document.getElementById(`number-${id}`).value.trim();
            const bank = document.getElementById(`bank-${id}`).value.trim();
            const verifyBtn = document.getElementById(`verify-btn-${id}`);

            if (name && number && bank) {
                verifyBtn.style.display = 'flex';
            } else {
                verifyBtn.style.display = 'none';
                resetVerification(id);
            }
        }
        
        
        // reset verification function 
        function resetVerification(id) {
            const verifyCell = document.getElementById(`verify-cell-${id}`);
            const verifyBtn = document.getElementById(`verify-btn-${id}`);
            
            // Remove any existing status display
            const existingStatus = verifyCell.querySelector('.verify-status');
            if (existingStatus) {
                existingStatus.remove();
            }
        }

        function verifyAccount(id) {
            const name = document.getElementById(`name-${id}`).value.trim();
            const number = document.getElementById(`number-${id}`).value.trim();
            const bank = document.getElementById(`bank-${id}`).value.trim();
            const bankCode = BANK_CODES[bank];
            const verifyBtn = document.getElementById(`verify-btn-${id}`);
            const verifyCell = document.getElementById(`verify-cell-${id}`);

            // Disable button and show loading
            verifyBtn.disabled = true;
            verifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verifying...';

            // Call Fincra verification API
            verifyAccountWithFincra(number, bankCode, name, id);
        }
        
        
        //verify accurount number api
        function verifyAccountWithFincra(accountNumber, bankCode, accountName, recipientId) {
            // Fincra verification endpoint
            const fincraUrl = 'https://sandboxapi.fincra.com/v1/accounts/resolve';
            
            const payload = {
                accountNumber: accountNumber,
                bankCode: bankCode
            };

            fetch(fincraUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer YOUR_FINCRA_API_KEY' // Replace with actual API key
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                const verifyBtn = document.getElementById(`verify-btn-${recipientId}`);
                const verifyCell = document.getElementById(`verify-cell-${recipientId}`);

                if (data.status === 'success' && data.data) {
                    // Verification successful
                    const status = document.createElement('div');
                    status.className = 'verify-status verified';
                    status.innerHTML = '<i class="fas fa-check-circle"></i> <span>Verified</span>';
                    
                    verifyCell.innerHTML = '';
                    verifyCell.appendChild(status);
                    
                    // Store verification data
                    document.getElementById(`name-${recipientId}`).dataset.verified = 'true';
                    showToast(`Account verified: ${data.data.accountName || accountName}`);
                } else {
                    // Verification failed
                    const status = document.createElement('div');
                    status.className = 'verify-status failed';
                    status.innerHTML = '<i class="fas fa-times-circle"></i> <span>Failed</span>';
                    
                    verifyCell.innerHTML = '';
                    verifyCell.appendChild(status);
                    
                    showToast('Account verification failed. Check details and try again.');
                }
            })
            .catch(error => {
                console.error('Verification error:', error);
                const verifyBtn = document.getElementById(`verify-btn-${recipientId}`);
                const verifyCell = document.getElementById(`verify-cell-${recipientId}`);

                // Show error status
                const status = document.createElement('div');
                status.className = 'verify-status failed';
                status.innerHTML = '<i class="fas fa-times-circle"></i> <span>Error</span>';
                
                verifyCell.innerHTML = '';
                verifyCell.appendChild(status);

                showToast('Verification error. Please check your API key.');
            });
        }

        function updateEmptyState() {
            const container = document.getElementById('recipientsContainer');
            const emptyState = document.getElementById('emptyState');
            const tableWrapper = document.getElementById('tableWrapper');
            
            if (container.children.length === 0) {
                emptyState.style.display = 'block';
                tableWrapper.style.display = 'none';
            } else {
                emptyState.style.display = 'none';
                tableWrapper.style.display = 'block';
            }
        }
        
        //save bulk payment function 

        function saveBulkPayment() {
            const recipients = [];
            const rows = document.querySelectorAll('#recipientsContainer tr');

            if (rows.length === 0) {
                showToast('Please add at least one recipient');
                return;
            }

            let isValid = true;

            rows.forEach((row, index) => {
                const id = index + 1;
                const name = document.getElementById(`name-${id}`)?.value.trim();
                const number = document.getElementById(`number-${id}`)?.value.trim();
                const bank = document.getElementById(`bank-${id}`)?.value.trim();

                if (!name || !number || !bank) {
                    isValid = false;
                    showToast(`Recipient ${id}: Please fill all fields`);
                    return;
                }

                recipients.push({
                    accountName: name,
                    accountNumber: number,
                    bankName: bank,
                    bankCode: BANK_CODES[bank]
                });
            });

            if (!isValid) return;

            // Create payload
            const payload = {
                batchId: generateBatchId(),
                timestamp: new Date().toISOString(),
                totalRecipients: recipients.length,
                recipients: recipients,
                metadata: {
                    source: 'DisPay Bulk Payment',
                    version: '1.0'
                }
            };

            // Show modal with payload
            showPayloadModal(payload);
        }
        
        
        //generate batchId function 
        function generateBatchId() {
            return `BATCH-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }

        function showPayloadModal(payload) {
            const modal = document.getElementById('payloadModal');
            const payloadText = document.getElementById('payloadText');
            payloadText.textContent = JSON.stringify(payload, null, 2);
            modal.classList.add('open');
            
            // Store payload globally for copying
            window.currentPayload = payload;
        }

        function closeModal() {
            document.getElementById('payloadModal').classList.remove('open');
        }

        function copyPayload() {
            const payloadText = document.getElementById('payloadText').textContent;
            navigator.clipboard.writeText(payloadText).then(() => {
                showToast('Payload copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy:', err);
                showToast('Failed to copy payload');
            });
        }

        function continueProcess() {
            closeModal();
            showToast('Payload ready for processing!');
            console.log('Payload:', window.currentPayload);
        }
        
        
        //send payment function 
        function sendPayment() {
            recipients = []
            
            const rows = document.querySelectorAll('#recipientsContainer tr');

            if (rows.length === 0) {
                showToast('Please add at least one recipient');
                return;
            }

            let isValid = true;
            
            for(let i =1; i <= recipientCount;i++){
                const id = i;
                
                let nameEl = document.getElementById(`name-${id}`);  
                
                const number = document.getElementById(`number-${id}`)?.value.trim();
                const bank = document.getElementById(`bank-${id}`)?.value.trim();
                alert()
                if (!number || !bank) {
                    isValid = false;
                    showToast(`Please fill all fields`);
                    return;
                }
                if(!nameEl) continue;
                const name = nameEl.value.trim();
                
                recipients.push({
                    id: id,
                    accountName: name,
                    accountNumber: number,
                    bankName: bank,
                    bankCode: BANK_CODES[bank]
                });
            };
            
            if (!recipients) return;

            // Simulate sending and generate results
            const results = recipients.map(recipient => {
                // Simulate random success/failure (you can replace with actual API call)
                const isSuccess = Math.random() > 0.2; // 80% success rate for demo
                
                return {
                    ...recipient,
                    status: isSuccess ? 'success' : 'failed',
                    timestamp: new Date().toISOString(),
                    message: isSuccess ? 'Payment processed successfully' : 'Payment failed - Invalid account'
                };
            });

            // Display results
            displayResults(results);
            showToast('Payment request submitted!');
        }
        
        //display results function 
        function displayResults(results) {
            const resultsSection = document.getElementById('resultsSection');
            const resultsGrid = document.getElementById('resultsGrid');
            const totalCount = document.getElementById('totalCount');
            const successCount = document.getElementById('successCount');
            const failedCount = document.getElementById('failedCount');

            // Clear previous results
            resultsGrid.innerHTML = '';

            // Calculate stats
            const successful = results.filter(r => r.status === 'success').length;
            const failed = results.filter(r => r.status === 'failed').length;

            totalCount.textContent = recipients.length;
            successCount.textContent = successful;
            failedCount.textContent = failed;

            // Display each result
            results.forEach(result => {
                const resultItem = document.createElement('div');
                resultItem.className = `result-item ${result.status}`;
                
                const icon = result.status === 'success' 
                    ? '<i class="fas fa-check-circle"></i>' 
                    : '<i class="fas fa-times-circle"></i>';
                
                const statusText = result.status === 'success' ? 'Success' : 'Failed';

                resultItem.innerHTML = `
                    <div class="result-status">
                        <span class="result-status-icon">${icon}</span>
                        <span class="result-status-text">${statusText}</span>
                    </div>
                    <div class="result-name">${result.accountName}</div>
                    <div class="result-details">
                        <div class="result-detail-row">
                            <span class="result-detail-label">Account:</span>
                            <span>${result.accountNumber}</span>
                        </div>
                        <div class="result-detail-row">
                            <span class="result-detail-label">Bank:</span>
                            <span>${result.bankName}</span>
                        </div>
                        <div class="result-detail-row">
                            <span class="result-detail-label">Code:</span>
                            <span>${result.bankCode}</span>
                        </div>
                    </div>
                `;

                resultsGrid.appendChild(resultItem);
            });

            // Show results section
            resultsSection.classList.remove('hidden');

            // Scroll to results
            setTimeout(() => {
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }, 100);
        }
        
        //show message function 
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.style.display = 'block';
            
            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        }

        // Close modal on background click
        document.getElementById('payloadModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });