IMPLEMENTATION_SUMMARY.md": 1,
      "title": "FDA Approves New Heart Device",
            "excerpt": "...",
                  "content": "Full article content...",
                        "category": "healthcare",
                              "image": "https://...",
                                    "source": "Medical Journal",
                                          "published_at": "2026-01-18T10:00:00Z",
                                                "is_bookmarked": false
                                                    }
                                                      ]
                                                      }
                                                      ```

                                                      ### 6. Notifications

                                                      #### Get Notifications
                                                      **GET** `/api/v1/notifications`

                                                      Query Parameters:
                                                      - `unread_only` (bool): Default false
                                                      - `limit` (int): Default 50

                                                      Response (200 OK):
                                                      ```json
                                                      {
                                                        "success": true,
                                                          "data": [
                                                              {
                                                                    "id": 1,
                                                                          "type": "deal_update",
                                                                                "title": "Deal Update",
                                                                                      "message": "CancerTech Inc has reached 70% funding goal!",
                                                                                            "related_id": 1,
                                                                                                  "related_type": "deal",
                                                                                                        "read": false,
                                                                                                              "created_at": "2026-01-18T21:00:00Z"
                                                                                                                  }
                                                                                                                    ]
                                                                                                                    }
                                                                                                                    ```
                                                                                                                    
                                                                                                                    #### Mark Notification as Read
                                                                                                                    **PUT** `/api/v1/notifications/{notification_id}/read`
                                                                                                                    
                                                                                                                    Response (200 OK):
                                                                                                                    ```json
                                                                                                                    {
                                                                                                                      "success": true,
                                                                                                                        "message": "Notification marked as read"
                                                                                                                        }
                                                                                                                        ```
                                                                                                                        
                                                                                                                        ## Error Handling
                                                                                                                        
                                                                                                                        All errors follow a standard format:
                                                                                                                        
                                                                                                                        ```json
                                                                                                                        {
                                                                                                                          "success": false,
                                                                                                                            "message": "Error message",
                                                                                                                              "errors": {
                                                                                                                                  "field_name": "Specific error for this field"
                                                                                                                                    },
                                                                                                                                      "timestamp": "2026-01-18T21:49:25.000Z"
                                                                                                                                      }
                                                                                                                                      ```
                                                                                                                                      
                                                                                                                                      ### Common Error Codes
                                                                                                                                      
                                                                                                                                      | Code | Message | Meaning |
                                                                                                                                      |------|---------|---------|
                                                                                                                                      | 400 | Bad Request | Invalid request data |
                                                                                                                                      | 401 | Unauthorized | Missing or invalid token |
                                                                                                                                      | 403 | Forbidden | Insufficient permissions |
                                                                                                                                      | 404 | Not Found | Resource not found |
                                                                                                                                      | 429 | Too Many Requests | Rate limit exceeded |
                                                                                                                                      | 500 | Internal Server Error | Server error |
                                                                                                                                      
                                                                                                                                      ## Rate Limiting
                                                                                                                                      
                                                                                                                                      Mobile endpoints are rate-limited:
                                                                                                                                      - **Standard**: 100 requests/hour per IP
                                                                                                                                      - **Authentication**: 5 attempts/minute
                                                                                                                                      - **File uploads**: 10/hour
                                                                                                                                      
                                                                                                                                      Rate limit info is returned in response headers:
                                                                                                                                      ```
                                                                                                                                      X-RateLimit-Limit: 100
                                                                                                                                      X-RateLimit-Remaining: 95
                                                                                                                                      X-RateLimit-Reset: 1642533600
                                                                                                                                      ```
                                                                                                                                      
                                                                                                                                      ## Pagination
                                                                                                                                      
                                                                                                                                      List endpoints support pagination:
                                                                                                                                      
                                                                                                                                      Request:
                                                                                                                                      ```
                                                                                                                                      GET /api/v1/deals?page=2&limit=20
                                                                                                                                      ```
                                                                                                                                      
                                                                                                                                      Response headers:
                                                                                                                                      ```
                                                                                                                                      X-Total-Count: 156
                                                                                                                                      X-Page: 2
                                                                                                                                      X-Page-Size: 20
                                                                                                                                      ```
                                                                                                                                      
                                                                                                                                      ## Timestamps
                                                                                                                                      All timestamps are in ISO 8601 format with UTC timezone: `2026-01-18T21:49:25.000Z`
                                                                                                                                      
                                                                                                                                      ## SDK/Client 
                                                                                                                              }
                                                                                                                        }
                                                                                                                    }
                                                              }
                                                          ]
                                                      }