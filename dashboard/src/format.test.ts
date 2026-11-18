import { expect, it } from "vitest";
import { money, words } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(money(61.5)).toBe("$61.50");
});

it("turns identifiers into words", () => {
  expect(words("trip_delay")).toBe("Trip delay");
  expect(words("emergency_medical")).toBe("Emergency medical");
});
