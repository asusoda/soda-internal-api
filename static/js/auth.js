document.addEventListener('DOMContentLoaded', function() {
    // Function to check if user is authenticated
    async function checkAuth() {
        try {
            const response = await fetch('/api/auth/check', {
                method: 'GET',
                credentials: 'include'  // Important for sending cookies
            });

            if (response.ok) {
                const data = await response.json();
                if (data.authenticated) {
                    // If on login page, redirect to dashboard
                    if (window.location.pathname === '/login') {
                        window.location.href = '/dashboard';
                    }
                } else {
                    // If not authenticated and not on login page, redirect to login
                    if (window.location.pathname !== '/login') {
                        window.location.href = '/login';
                    }
                }
            } else {
                // If error and not on login page, redirect to login
                if (window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            // If error and not on login page, redirect to login
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
    }

    // Run auth check
    checkAuth();
}); 