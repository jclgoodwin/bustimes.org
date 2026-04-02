import { Transformer } from "@parcel/plugin";

export default new Transformer({
  async transform({ asset }) {
    asset.bundleBehavior = "isolated";

    let code = await asset.getCode();

    code = JSON.stringify(JSON.parse(code));

    asset.setCode(code);

    return [asset];
  },
});
