import React from "react";
import { Route, Switch } from "wouter";

import BigMap, { MapMode } from "./BigMap";

export default function MapRouter() {
  return (
    <Switch>
      <Route path="/trips/:tripId">
        {(params) => (
          <BigMap
            mode={MapMode.Trip}
            trip={window.STOPS}
            tripId={params.tripId}
          />
        )}
      </Route>
      <Route path="/operators/:operatorSlug/map">
        <BigMap
          mode={MapMode.Operator}
          noc={window.OPERATOR_ID || (window.STOPS?.operator?.noc as string)}
        />
      </Route>
      <Route path="/map">
        <BigMap mode={MapMode.Slippy} />
      </Route>
    </Switch>
  );
}
