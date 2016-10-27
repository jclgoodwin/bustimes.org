vcl 4.0;

backend default {
    .host = "127.0.0.1";
    .port = "8080";
}

sub vcl_recv {
    if (req.url ~ "^/(admin/|contact|awin-transaction)") {
        return (pass);
    }

#    if (req.url ~ "/departures" &&
#        (req.http.User-Agent ~ "(?i)(ads|google|bing|msn|yandex|baidu|ro|career|seznam|)bot" ||
#         req.http.User-Agent ~ "(?i)(baidu|jike|symantec)spider" ||
#         req.http.User-Agent ~ "(?i)scanner|slurp|bing" ||
#         req.http.User-Agent ~ "(?i)(web)crawler")
#    ) {
#        return (synth (200, ""));
#    }

    unset req.http.Cookie;
}

sub vcl_backend_response {
    if (bereq.url ~ "^/stops/" && bereq.url !~ "/departures") {
        set beresp.do_esi = true;
    }

    if (bereq.url !~ "^/(admin/|contact)") {
        unset beresp.http.set-cookie;

        if (bereq.url !~ "/departures" && beresp.status >= 200 && beresp.status < 400) {
            set beresp.ttl = 2h;
        }
    }

    set beresp.grace = 6h;
}

sub vcl_synth {
    if (resp.status == 200) {
        synthetic ({""});
        return (deliver);
    }
}
