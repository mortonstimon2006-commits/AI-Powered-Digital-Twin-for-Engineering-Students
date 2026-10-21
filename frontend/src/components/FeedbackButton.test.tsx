import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FeedbackButton } from "@/components/FeedbackButton";
import { axeViolations, jsonResponse, renderWithProviders } from "@/test/utils";

afterEach(() => vi.restoreAllMocks());

describe("FeedbackButton", () => {
  it("requires a rating, pre-selects the area from the page and sends the feedback", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ message: "Thank you" }));
    const user = userEvent.setup();
    renderWithProviders(<FeedbackButton />, { route: "/app/gaps" });

    await user.click(screen.getByRole("button", { name: /send feedback/i }));
    const dialog = await screen.findByRole("dialog", { name: "Send feedback" });
    expect(await axeViolations(dialog)).toEqual([]);
    expect(screen.getByLabelText("What is it about?")).toHaveValue("gap_analysis");
    const send = screen.getAllByRole("button", { name: "Send feedback" }).at(-1)!;
    expect(send).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "4 – Useful" }));
    await user.type(screen.getByLabelText("Comment"), "  Clear and helpful  ");
    await user.click(send);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/api/v1/feedback"));
    expect(call).toBeDefined();
    expect(JSON.parse(String(call![1]!.body))).toEqual({ target_type: "gap_analysis", target_id: "/app/gaps", rating: 4, comment: "Clear and helpful" });
  });
});
