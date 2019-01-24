vcl 4.0;

backend default {
    .host = "127.0.0.1";
    .port = "8081";
}

backend bustimesio {
    .host = "127.0.0.1";
    .port = "8082";
}

backend supermarket {
    .host = "127.0.0.1";
    .port = "8000";
}

backend basiltherat {
    .host = "127.0.0.1";
    .port = "8083";
}

backend tileserver {
    .host = "127.0.0.1";
    .port = "8080";
}

sub vcl_recv {
    if (req.http.host == "bustimes.io") {
        set req.backend_hint = bustimesio;
    } elif (req.http.host == "www.supermarketmarket.co.uk") {
        set req.backend_hint = supermarket;
    } elif (req.http.host == "hygieneratings.co.uk") {
        set req.backend_hint = basiltherat;
    } elif (req.url ~ "^/styles/") {
        set req.backend_hint = tileserver;
    }

    if (req.url ~ "^/(admin/|contact|awin-transaction)") {
        return (pass);
    }

    if (req.http.User-Agent ~ "(?i)grapeshotcrawler|bingbot|mj12bot|slurp|ahrefsbot|dotbot|semrushbot|yandexbot") {
        set req.http.X-Bot = "bot";
    }

    unset req.http.Cookie;
}

sub vcl_backend_response {
    if (bereq.url !~ "^/(admin/|contact)") {
        unset beresp.http.set-cookie;

        if (beresp.status >= 200 && beresp.status < 400) {
            if (bereq.url ~ "^/stops/") {
                set beresp.ttl = 30s;

                if (beresp.http.Vary) {
                   set beresp.http.Vary = beresp.http.Vary + ", X-Bot";
                } else {
                    set beresp.http.Vary = "X-Bot";
                }
            } elif (bereq.url ~ "^/vehicles\.json") {
                set beresp.ttl = 5s;
            } elif (bereq.url ~ "^/styles/") {
                set beresp.ttl = 30d;
            } else {
                set beresp.ttl = 1h;
            }
        }

    }
}

sub vcl_deliver {
    if (req.url ~ "/stops/" && resp.status >= 200 && resp.status < 400) {
        set resp.http.X-Accel-Buffering = "no";
    }
}
