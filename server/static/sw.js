/* Service Worker for Chatter push notifications */

self.addEventListener('push', event => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (e) {
        data = { title: 'Новое сообщение', body: '' };
    }

    event.waitUntil(
        self.registration.showNotification(data.title || 'Новое сообщение', {
            body: data.body || '',
            icon: '/static/favicon.svg',
            tag: 'chatter-' + (data.conv_id || ''),
            data: { conv_id: data.conv_id },
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
            for (const client of list) {
                if (client.url.includes('/chat') && 'focus' in client) {
                    return client.focus();
                }
            }
            return clients.openWindow('/chat');
        })
    );
});
