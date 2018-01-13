vcl 4.0;

backend default {
    .host = "127.0.0.1";
    .port = "8081";
}

backend bustimesio {
    .host = "127.0.0.1";
    .port = "8082";
}

backend tileserver {
    .host = "127.0.0.1";
    .port = "8080";
}

sub vcl_recv {
    if (req.http.host == "bustimes.io") {
        set req.backend_hint = bustimesio;
    } elif (req.url ~ "^/styles/") {
        set req.backend_hint = tileserver;
    }

    if (req.url ~ "^/(admin/|contact|awin-transaction)") {
        return (pass);
    }

    if (req.url ~ "^/services/" && req.http.Cookie ~ "sessionid") {
        return (pass);
    }

    unset req.http.Cookie;
}

sub vcl_backend_response {
    if (bereq.url !~ "^/(admin/|contact)") {
        unset beresp.http.set-cookie;

        if (beresp.status >= 200 && beresp.status < 400) {
            if (bereq.url ~ "^/stops/") {
                set beresp.ttl = 30s;
            } elif (bereq.url ~ "^/styles/") {
                set beresp.ttl = 30d;
            } else {
                set beresp.ttl = 1h;
            }
        }

    }
}
