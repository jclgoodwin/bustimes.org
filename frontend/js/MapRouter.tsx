import React from "react";
import { Route, Switch } from "wouter";

import BigMap from "./BigMap";
import TripMap from "./TripMap";
import OperatorMap from "./OperatorMap";

export default function MapRouter() {
  return (
    <Switch>
      <Route path="/trips/:tripId">
        {(params) => <TripMap tripId={params.tripId} />}
      </Route>
      <Route path="/operators/:operatorSlug/map">
        {(params) => <OperatorMap noc={params.operatorSlug} />}
      </Route>
      <Route path="/map">
        <BigMap />
      </Route>
    </Switch>
  );
}
