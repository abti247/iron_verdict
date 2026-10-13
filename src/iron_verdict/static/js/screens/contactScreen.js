// Contact screen: the contact form, sent to Web3Forms. A fresh, empty form
// each time the screen opens (it is rendered with x-if).

export function contactScreen() {
    return {
        contactName: '',
        contactEmail: '',
        contactMessage: '',
        contactStatus: 'idle',  // 'idle' | 'loading' | 'success' | 'error'

        async submitContact() {
            this.contactStatus = 'loading';
            try {
                const res = await fetch('https://api.web3forms.com/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    body: JSON.stringify({
                        access_key: '2e92ea27-be19-4996-83c9-0b33fcb63419',
                        name: this.contactName,
                        email: this.contactEmail,
                        message: this.contactMessage,
                    })
                });
                const data = await res.json();
                this.contactStatus = data.success ? 'success' : 'error';
            } catch (_e) {
                this.contactStatus = 'error';
            }
        },
    };
}
