import React from "react";
import { Route, Switch } from "wouter";

import BigMap from "./BigMap";
import TripMap from "./TripMap";
import OperatorMap from "./OperatorMap";

export default function MapRouter() {
  return (
    <Switch>
      <Route path="/trips/:tripId">
        {(params) => <TripMap trip={window.STOPS} tripId={params.tripId} />}
      </Route>
      <Route path="/operators/:operatorSlug/map">
        <OperatorMap noc={window.OPERATOR_ID || window.STOPS?.operator?.noc as string} />
      </Route>
      <Route path="/map">
        <BigMap />
      </Route>
    </Switch>
  );
}
