import { Router, Request, Response } from "express";
import mangaRoutes from "./manga.routes";
import softkomikRoutes from "./softkomik.routes";

import { authenticate } from "../middleware/auth";

const router = Router();

// Mount routes
router.use("/manga", authenticate, mangaRoutes);
router.use("/softkomik", authenticate, softkomikRoutes);

// Health check route
router.get("/health", (_req: Request, res: Response) => {
  res.status(200).json({
    success: true,
    version: "1.0.0",
    authenticate: true,
    message: "Shinigami + Softkomik API is running",
    timestamp: new Date().toISOString(),
  });
});

export default router;
