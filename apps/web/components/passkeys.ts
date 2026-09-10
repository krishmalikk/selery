import { SeleryClient } from '@selery/shared';

export function supportsPasskeys() {
  return typeof window !== 'undefined' && window.isSecureContext && !!window.PublicKeyCredential;
}

function decode(value: string): ArrayBuffer {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')), c => c.charCodeAt(0)).buffer;
}
function encode(value: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
type Descriptor = Omit<PublicKeyCredentialDescriptor, 'id'> & {id: string};
type Creation = Omit<PublicKeyCredentialCreationOptions, 'challenge' | 'user' | 'excludeCredentials'> & {
  challenge: string; user: Omit<PublicKeyCredentialUserEntity, 'id'> & {id: string}; excludeCredentials?: Descriptor[];
};
type RequestOptions = Omit<PublicKeyCredentialRequestOptions, 'challenge' | 'allowCredentials'> & {
  challenge: string; allowCredentials?: Descriptor[];
};

function failure(error: unknown): Error {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError' || error.name === 'AbortError')
      return new Error('Passkey unlock was canceled, timed out, or no matching passkey was available. Try again or use your workspace password.');
    if (error.name === 'InvalidStateError') return new Error('This passkey is already registered. Use it to open the workspace.');
    if (error.name === 'SecurityError') return new Error('Passkeys are not configured for this website address. Use your usual Selery URL or your workspace password.');
  }
  return error instanceof Error ? error : new Error('Passkey request failed. Your password still works.');
}

export async function registerPasskey(api: SeleryClient, password: string, name: string) {
  if (!supportsPasskeys()) throw new Error('Passkeys require a supported browser and HTTPS (or localhost for development).');
  try {
    const start = await api.passkeyRegisterOptions(password, name);
    const options: Creation = JSON.parse(start.options_json);
    const credential = await navigator.credentials.create({publicKey: {...options, challenge: decode(options.challenge),
      user: {...options.user, id: decode(options.user.id)},
      excludeCredentials: options.excludeCredentials?.map(c => ({...c, id: decode(c.id)}))}}) as PublicKeyCredential | null;
    if (!credential) throw new Error('No passkey was created.');
    const response = credential.response as AuthenticatorAttestationResponse;
    return await api.passkeyRegisterVerify(start.ceremony_id, JSON.stringify({id: credential.id, rawId: encode(credential.rawId),
      type: credential.type, response: {clientDataJSON: encode(response.clientDataJSON), attestationObject: encode(response.attestationObject),
        transports: response.getTransports?.() ?? []}, clientExtensionResults: credential.getClientExtensionResults()}));
  } catch (error) { throw failure(error); }
}

export async function signInWithPasskey(api: SeleryClient) {
  if (!supportsPasskeys()) throw new Error('This browser does not support passkeys. Use your workspace password.');
  try {
    const start = await api.passkeyLoginOptions();
    const options: RequestOptions = JSON.parse(start.options_json);
    const credential = await navigator.credentials.get({publicKey: {...options, challenge: decode(options.challenge),
      allowCredentials: options.allowCredentials?.map(c => ({...c, id: decode(c.id)}))}}) as PublicKeyCredential | null;
    if (!credential) throw new Error('No passkey was selected.');
    const response = credential.response as AuthenticatorAssertionResponse;
    return await api.passkeyLoginVerify(start.ceremony_id, JSON.stringify({id: credential.id, rawId: encode(credential.rawId),
      type: credential.type, response: {clientDataJSON: encode(response.clientDataJSON), authenticatorData: encode(response.authenticatorData),
        signature: encode(response.signature), userHandle: response.userHandle ? encode(response.userHandle) : null},
      clientExtensionResults: credential.getClientExtensionResults()}));
  } catch (error) { throw failure(error); }
}
