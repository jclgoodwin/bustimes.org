import React from "react";
import renderer from "react-test-renderer";
import { Delay } from "../VehiclePopup";

it("shows delay", () => {
  const component = renderer.create(<Delay item={{ delay: 212 }} />);
  let tree = component.toJSON();
  expect(tree).toMatchSnapshot();

  component.update(<Delay item={{ delay: -230 }} />);
  tree = component.toJSON();
  expect(tree).toMatchSnapshot();

  component.update(<Delay item={{ delay: 20 }} />);
  tree = component.toJSON();
  expect(tree).toMatchSnapshot();

  component.update(<Delay item={{ delay: -20 }} />);
  tree = component.toJSON();
  expect(tree).toMatchSnapshot();

  component.update(<Delay item={{}} />);
  tree = component.toJSON();
  expect(tree).toMatchSnapshot();
});
