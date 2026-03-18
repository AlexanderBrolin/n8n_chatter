import type {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class N8nFrontApi implements ICredentialType {
	name = 'n8nFrontApi';
	displayName = 'N8nFront Bot API';
	documentationUrl = '';
	properties: INodeProperties[] = [
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: '',
			placeholder: 'https://chat.example.com',
			description: 'URL вашего N8nFront сервера (без /api/bot)',
			required: true,
		},
		{
			displayName: 'Bot Token',
			name: 'botToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			description: 'API-токен бота (из админки N8nFront)',
			required: true,
		},
	];

	test: ICredentialTestRequest = {
		request: {
			url: '={{$credentials.baseUrl.replace(/\\/+$/, "") + "/api/bot/" + $credentials.botToken + "/getMe"}}',
			method: 'GET',
		},
	};
}
