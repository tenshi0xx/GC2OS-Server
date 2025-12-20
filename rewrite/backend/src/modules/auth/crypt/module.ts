import * as crypto from 'crypto'
import { error } from "console";
/* var init */

// Found in: aesManager::initialize()
// Used for: Crypting parameter bytes sent by client
// Credit: https://github.com/Walter-o/gcm-downloader

const AES_CBC_KEY = Buffer.from("oLxvgCJjMzYijWIldgKLpUx5qhUhguP1", 'utf-8')

//Found in: aesManager::decryptCBC() and aesManager::encryptCBC()
// Used for: Crypting parameter bytes sent by client
// Credit: https://github.com/Walter-o/gcm-downloader

const AES_CBC_IV = Buffer.from("6NrjyFU04IO9j9Yo", 'utf-8')
const ALGORITHM = 'aes-256-cbc'

/**
 *  * Decrypt AES hex string
 * @param {string} hexData - Hex string to decrypt
 * @param {Buffer} key - AES key (optional)
 * @param {Buffer} iv - AES IV (optional)
 * @returns {Buffer} - decrypted bytes
 */

export function decryptAES(hexData: string, key = AES_CBC_KEY, iv = AES_CBC_IV) {
    const encrypted = Buffer.from(hexData, 'hex');

    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    decipher.setAutoPadding(false);
    
    const decrypted = Buffer.concat([
        decipher.update(encrypted),
        decipher.final()
    ]);
    
    return decrypted;
}
/* Encryption Function*/
export function encryptAES(data: Buffer | string, key = AES_CBC_KEY, iv = AES_CBC_IV) {
    // Idk how do i implement it
    let buffer = Buffer.isBuffer(data) ? data : Buffer.from(data, 'utf-8');
    while (buffer.length % 16 !== 0) {
        buffer = Buffer.concat([buffer, Buffer.from([0x00])]);
    }
    const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
    cipher.setAutoPadding(false);
    return Buffer.concat([cipher.update(buffer), cipher.final()]).toString('hex')
}