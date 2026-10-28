import { Request, Response, NextFunction } from "express";
import dotenv from "dotenv";

dotenv.config();

export const authenticate = (
    req: Request,
    res: Response,
    next: NextFunction
) => {
    const apiKey = req.headers["x-api-key"];
    const validApiKey = process.env.API_KEY;
    console.log(`Received Key: ${apiKey}`);

    if (!apiKey || apiKey !== validApiKey) {
        res.status(401).json({
            success: false,
            message: "Unauthorized: Invalid or missing API Key",
        });
        return;
    }

    next();
};
