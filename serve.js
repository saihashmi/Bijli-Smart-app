// static server with gzip, like Apache mod_deflate on Hostinger
const http=require('http'),fs=require('fs'),path=require('path'),zlib=require('zlib');
const T={'.html':'text/html','.js':'application/javascript','.css':'text/css','.woff2':'font/woff2','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg','.txt':'text/plain','.xml':'application/xml'};
http.createServer((q,r)=>{let p=decodeURIComponent(q.url.split('?')[0]);if(p.endsWith('/'))p+='index.html';const f=path.join(__dirname,'dist',p);
fs.readFile(f,(e,b)=>{if(e){r.writeHead(404);return r.end()}const ext=path.extname(f);const h={'Content-Type':T[ext]||'application/octet-stream','Cache-Control':ext==='.html'?'no-cache':'public, max-age=31536000, immutable'};
if(/gzip/.test(q.headers['accept-encoding']||'')&&/html|javascript|css|xml|plain/.test(h['Content-Type'])){h['Content-Encoding']='gzip';b=zlib.gzipSync(b)}r.writeHead(200,h);r.end(b)})}).listen(8080);
