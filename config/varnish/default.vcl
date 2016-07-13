vcl 4.0;

backend default {
    .host = "127.0.0.1";
    .port = "8080";
}

sub vcl_recv {
    if (req.url ~ "^/(admin/|contact)") {
        return (pass);
    }

    unset req.http.Cookie;
}

sub vcl_backend_response {
    if (bereq.url !~ "^/(admin/|contact)") {
        unset beresp.http.set-cookie;

        if (bereq.url !~ "/departures" && beresp.status >= 200 && beresp.status < 400) {
            set beresp.ttl = 2h;
        }
    }

    set beresp.grace = 6h;
}

sub vcl_deliver {
}
