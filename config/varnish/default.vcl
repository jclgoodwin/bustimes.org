# Marker to tell the VCL compiler that this VCL has been adapted to the
# new 4.0 format.
vcl 4.0;

# Default backend definition. Set this to point to your content server.
backend default {
    .host = "127.0.0.1";
    .port = "8080";
}

acl purge {
    "localhost";
    "10.131.0.0"/16;
}

sub vcl_recv {
    # Happens before we check if we have this in cache already.
    #
    # Typically you clean up the request here, removing cookies you don't need,
    # rewriting the request, etc.

    if (req.method == "BAN") {
        if (!client.ip ~ purge) {
            return(synth(405,"Not allowed."));
        }
        ban("obj.http.url ~ ^" + req.url);
        return (synth(200, "Ban added"));
    }

    if (req.url ~ "^/(admin/|accounts/|siri|contact|awin-transaction)" || req.url ~ "/edit") {
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

    if (bereq.url !~ "^/(admin/|accounts/|contact)" && bereq.url !~ "/edit") {
        unset beresp.http.set-cookie;

        set beresp.http.url = bereq.url;

        if (beresp.status >= 200 && beresp.status < 400) {
            if (bereq.url ~ "^/stops/") {
                set beresp.ttl = 1m;
            } elif (bereq.url ~ "/(journeys|locations)") {
                set beresp.ttl = 10s;
            } elif (bereq.url ~ "/vehicles") {
                set beresp.ttl = 5m;
            } else {
                set beresp.ttl = 30m;
                set beresp.grace = 10m;
            }
        }
    }
}
