declare global {
  interface ObjectConstructor {
    hasOwn(o: object, key: PropertyKey): boolean;
  }
}

if (typeof Object.hasOwn !== "function") {
  Object.hasOwn = (o, key) => Object.prototype.hasOwnProperty.call(o, key);
}

export {};
