package com.lqq.supportflow.shared;

/**
 * Raised when a local runtime cannot access the secure material required to
 * protect credentials. The public API deliberately does not reveal which
 * environment variable, keychain item, or cryptographic provider failed.
 */
public class LocalSecureStorageUnavailableException extends RuntimeException {

    public LocalSecureStorageUnavailableException() {
        super("local secure storage is unavailable");
    }
}
