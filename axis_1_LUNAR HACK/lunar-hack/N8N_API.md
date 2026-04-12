{
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "send-email",
        "responseMode": "responseNode",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [
        -208,
        80
      ],
      "id": "8bcfda5e-79b1-4cd2-b5a5-97513c64f685",
      "name": "Webhook Trigger",
      "webhookId": "send-email-trigger",
      "onError": "continueRegularOutput"
    },
    {
      "parameters": {
        "sendTo": "={{$input.item.json.body.to}}",
        "subject": "={{$input.item.json.body.subject}}",
        "message": "={{$input.item.json.body.body_html}}",
        "options": {}
      },
      "type": "n8n-nodes-base.gmail",
      "typeVersion": 2.2,
      "position": [
        0,
        80
      ],
      "id": "6c799a75-aefb-4f90-8eb4-98bb90a91a89",
      "name": "Send a message",
      "webhookId": "3497c1a1-283f-4b21-a0de-f50e0d4e0870",
      "credentials": {
        "gmailOAuth2": {
          "id": "gL1aPMbFcqgFxT3c",
          "name": "Gmail account"
        }
      },
      "onError": "continueErrorOutput"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={ \"success\": true, \"message\": \"Email sent successfully\" }",
        "options": {
          "responseCode": 200
        }
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [
        288,
        -16
      ],
      "id": "cdb2aa65-fe09-4019-a43b-000b5be1d651",
      "name": "Success Response"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={ \"success\": false, \"error\": \"Failed to send email\", \"details\": \"{{$input.item.json.error.message}}\" }",
        "options": {
          "responseCode": 500
        }
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [
        288,
        208
      ],
      "id": "c8c7275d-643c-4960-a4e5-f8d541134d55",
      "name": "Error Response"
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [
        [
          {
            "node": "Send a message",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Send a message": {
      "main": [
        [
          {
            "node": "Success Response",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Error Response",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "pinData": {},
  "meta": {
    "templateCredsSetupCompleted": true,
    "instanceId": "ac9dd90b9209326e64c7426e7ca5e5f2eb95d409dc4c3c27aab4222d359a5c58"
  }
}


