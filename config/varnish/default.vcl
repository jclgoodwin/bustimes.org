# Marker to tell the VCL compiler that this VCL has been adapted to the
# new 4.0 format.
vcl 4.0;

# Default backend definition. Set this to point to your content server.
backend default {
    .host = "127.0.0.1";
    .port = "8080";
}

sub vcl_recv {
    # Happens before we check if we have this in cache already.
    #
    # Typically you clean up the request here, removing cookies you don't need,
    # rewriting the request, etc.

    if (req.url ~ "^/(admin/|contact|awin-transaction)" || req.url ~ "/edit") {
        return (pass);
    }

    # special features on fleet lists for logged in users
    if (req.http.Cookie ~ "sessionid" && req.url ~ "operator" && req.url ~ "vehicles") {
        return (pass);
    }

    unset req.http.Cookie;
}

sub vcl_backend_response {
    # Happens after we have read the response headers from the backend.
    #
    # Here you clean the response headers, removing silly Set-Cookie headers
    # and other mistakes your backend does.

    if (bereq.url !~ "^/(admin/|contact)" || req.url !~ "/edit") {
        unset beresp.http.set-cookie;

        if (beresp.status >= 200 && beresp.status < 400) {
            if (bereq.url ~ "^/stops/") {
                set beresp.ttl = 50s;
            } elif (bereq.url ~ "/(vehicles|journeys/)") {
                set beresp.ttl = 6s;
            } else {
                set beresp.ttl = 1h;
            }
        }
    }
}
