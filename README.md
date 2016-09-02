# hackle box

work in progress

Generating self signed ssl cert:

    openssl genrsa -des3 -passout pass:x -out server.pass.key 2048
    openssl rsa -passin pass:x -in server.pass.key -out server.key
    rm server.pass.key 
    
    openssl req -new -subj "/C=GB/ST=NA/L=NA/O=NA/CN=<DOMAIN>" -key server.key -out server.csr
    # openssl req -in server.csr -noout -text
    openssl x509 -req -sha256 -days 365 -in server.csr -signkey server.key -out server.crt
    rm server.csr
