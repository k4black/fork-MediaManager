import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ parent }) => {
	const { loginData } = await parent();
	if (!loginData?.registration_enabled) {
		redirect(307, resolve('/login', {}));
	}
};
