const http = require('http');

const options = {
  hostname: 'localhost',
  port: 3000,
  path: '/dashboard',
  method: 'GET',
};

const req = http.request(options, (res) => {
  console.log('STATUS:', res.statusCode);
  console.log('HEADERS:', res.headers);
});

req.on('error', (e) => {
  console.error('problem with request:', e.message);
});
req.end();
