/**
 * Validation Middleware
 */

import { Request, Response, NextFunction } from 'express';
import { validationResult, ValidationError } from 'express-validator';

/**
 * Validate request using express-validator
 */
export function validate(req: Request, res: Response, next: NextFunction) {
  const errors = validationResult(req);
  
  if (!errors.isEmpty()) {
    const errorDetails: Record<string, string[]> = {};
    
    errors.array().forEach((error: ValidationError) => {
      const field = 'path' in error ? error.path : 'unknown';
      if (!errorDetails[field]) {
        errorDetails[field] = [];
      }
      errorDetails[field].push(error.msg);
    });
    
    return res.status(422).json({
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Validation failed',
        details: errorDetails,
      },
    });
  }
  
  next();
}
