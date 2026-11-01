// Category: Security Vulnerabilities (Success Case)
// Expected Result: Do not hardcode sensitive information; use config or environment variables

#include <iostream>
#include <string>
#include <cstdlib>

bool authenticate(const std::string& username, const std::string& password) {
    // SUCCESS: In a real system, you would check a hash. 
    // Here we simulate not having hardcoded strings in the code.
    // (Example: fetching from a secure vault or environment)
    char* envUser = std::getenv("APP_ADMIN_USER");
    char* envPass = std::getenv("APP_ADMIN_PASS");
    
    if (envUser && envPass) {
        return (username == envUser && password == envPass);
    }
    return false;
}

int main() {
    std::string user, pass;
    
    std::cout << "Username: ";
    std::cin >> user;
    std::cout << "Password: ";
    std::cin >> pass;
    
    if (authenticate(user, pass)) {
        std::cout << "Access granted!" << std::endl;
    } else {
        std::cout << "Access denied." << std::endl;
    }
    
    return 0;
}
