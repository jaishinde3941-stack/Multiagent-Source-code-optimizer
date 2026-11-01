// Category: Security Vulnerabilities
// Error: Integer overflow leading to buffer issue

#include <iostream>
#include <cstdlib>

int main() {
    unsigned int size;
    
    std::cout << "Enter size: ";
    std::cin >> size;
    
    // ERROR: If size is very large, size + 1 can overflow to 0
    char* buffer = (char*)malloc(size + 1);
    
    if (buffer == nullptr) {
        std::cout << "Allocation failed" << std::endl;
        return 1;
    }
    
    // Could write more than allocated if overflow occurred
    for (unsigned int i = 0; i <= size; i++) {
        buffer[i] = 'A';
    }
    
    buffer[size] = '\0';
    std::cout << "Buffer: " << buffer << std::endl;
    
    free(buffer);
    return 0;
}
