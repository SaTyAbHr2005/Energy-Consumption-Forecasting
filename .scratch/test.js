const options = { path: '/' };
const opts = Object.entries({
    ...options,
    path: '/',
    maxAge: undefined,
    expires: undefined,
})
.filter(([_, v]) => v != null)
.map(([k, v]) => (v === true ? k : `${k}=${v}`))
.join('; ');
console.log(opts);
